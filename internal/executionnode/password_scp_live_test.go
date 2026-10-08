//go:build passwordscpqa

package executionnode

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/crypto/ssh"
	"platform-installer/internal/sshpassword"
)

func TestMain(m *testing.M) {
	if sshpassword.Dispatch() {
		return
	}
	os.Exit(m.Run())
}

// Actual installed OpenSSH SCP and ASKPASS connect to an isolated password-only
// SSH endpoint. Its exec handler runs the installed SCP server, not a fake wire
// response. Synthetic credentials never leave this test's memory/helper stream.
func TestInstalledPasswordSCPUploadDownloadAndPinnedFailure(t *testing.T) {
	scp, err := exec.LookPath("scp")
	if err != nil {
		t.Skip("installed OpenSSH SCP unavailable")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 35*time.Second)
	defer cancel()
	root := t.TempDir()
	_, key, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	signer, err := ssh.NewSignerFromKey(key)
	if err != nil {
		t.Fatal(err)
	}
	config := &ssh.ServerConfig{PasswordCallback: func(c ssh.ConnMetadata, p []byte) (*ssh.Permissions, error) {
		if c.User() == "qa" && bytes.Equal(p, []byte("synthetic-scp-only")) {
			return nil, nil
		}
		return nil, fmt.Errorf("authentication rejected")
	}}
	config.AddHostKey(signer)
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	defer func() { cancel(); listener.Close(); wg.Wait() }()
	wg.Add(1)
	go func() {
		defer wg.Done()
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			wg.Add(1)
			go func() {
				defer wg.Done()
				defer conn.Close()
				_ = conn.SetDeadline(time.Now().Add(30 * time.Second))
				session, channels, requests, err := ssh.NewServerConn(conn, config)
				if err != nil {
					return
				}
				defer session.Close()
				go ssh.DiscardRequests(requests)
				for request := range channels {
					if request.ChannelType() != "session" {
						request.Reject(ssh.UnknownChannelType, "unsupported")
						continue
					}
					channel, reqs, err := request.Accept()
					if err != nil {
						return
					}
					func() {
						defer channel.Close()
						for req := range reqs {
							if req.Type != "exec" {
								req.Reply(false, nil)
								continue
							}
							var payload struct{ Command string }
							if ssh.Unmarshal(req.Payload, &payload) != nil {
								req.Reply(false, nil)
								return
							}
							parts := strings.Fields(payload.Command)
							if len(parts) != 3 || parts[0] != "scp" || (parts[1] != "-t" && parts[1] != "-f") || parts[2] != "fixture" {
								req.Reply(false, nil)
								return
							}
							req.Reply(true, nil)
							command := exec.CommandContext(ctx, scp, parts[1:]...)
							command.Dir = root
							stdin, err := command.StdinPipe()
							if err != nil {
								return
							}
							copied := make(chan struct{})
							go func() { defer close(copied); defer stdin.Close(); _, _ = io.Copy(stdin, channel) }()
							command.Stdout = channel
							command.Stderr = channel.Stderr()
							status := uint32(0)
							if command.Run() != nil {
								status = 1
							}
							channel.SendRequest("exit-status", false, ssh.Marshal(struct{ Status uint32 }{status}))
							channel.Close()
							<-copied
							return
						}
					}()
				}
			}()
		}
	}()
	_, portText, _ := net.SplitHostPort(listener.Addr().String())
	port, _ := strconv.Atoi(portText)
	known := filepath.Join(root, "known_hosts")
	if err := os.WriteFile(known, append([]byte("[127.0.0.1]:"+portText+" "), ssh.MarshalAuthorizedKey(signer.PublicKey())...), 0600); err != nil {
		t.Fatal(err)
	}
	transport := OpenSSHTransport{IsolatedHostKeyTrust: true, Password: func(_ context.Context, use func([]byte) error) error {
		p := []byte("synthetic-scp-only")
		defer func() {
			for i := range p {
				p[i] = 0
			}
		}()
		return use(p)
	}}
	node := Node{Address: "127.0.0.1", Port: uint16(port), User: "qa", HostKey: HostKeyPolicy{KnownHosts: known}}
	source := filepath.Join(root, "source")
	download := filepath.Join(root, "download")
	fixture := []byte("nonsecret SCP fixture\n")
	if err := os.WriteFile(source, fixture, 0600); err != nil {
		t.Fatal(err)
	}
	for _, pair := range [][2]string{{source, transport.destination(node, "fixture")}, {transport.destination(node, "fixture"), download}} {
		args := append(transport.scpBase(node, ""), "-O", "--", pair[0], pair[1])
		if _, err := transport.run(ctx, "scp", args, nil); err != nil {
			t.Fatal(err)
		}
	}
	got, err := os.ReadFile(download)
	if err != nil || !bytes.Equal(got, fixture) {
		t.Fatal("SCP round trip differs")
	}
	wrong := transport
	wrong.Password = func(_ context.Context, use func([]byte) error) error { return use([]byte("synthetic-wrong")) }
	if _, err := wrong.run(ctx, "scp", append(wrong.scpBase(node, ""), "-O", "--", source, wrong.destination(node, "fixture")), nil); err == nil {
		t.Fatal("incorrect password accepted")
	}
	if err := os.WriteFile(known, []byte(""), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := transport.run(ctx, "scp", append(transport.scpBase(node, ""), "-O", "--", source, transport.destination(node, "fixture")), nil); err == nil {
		t.Fatal("missing host pin accepted")
	}
	t.Log("Installed password-only OpenSSH SCP upload/download and pin rejection PASS")
}
