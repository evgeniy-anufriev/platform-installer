package executionnode

import (
	"bytes"
	"context"
	"errors"
	"strings"
)

// Authentication and the command run under the same shell parent for each
// invocation, including command substitutions and pipelines. Unsupported sudo
// timestamp policy fails closed at the subsequent noninteractive command.
const executionSudoFunction = `sudo() {
 [ "$1" = -n ] || return 64
 shift
 printf '%s\n' "$_platform_sudo_password" | command sudo -S -p '' -v || return
 command sudo -n "$@"
 _platform_sudo_status=$?
 return "$_platform_sudo_status"
}
`

func (t OpenSSHTransport) withSudoInput(ctx context.Context, program string, args []string, input []byte, run func(string, []string, []byte) ([]byte, error)) ([]byte, error) {
	script := program == "sh" && len(args) > 0 && args[0] == "-s" && bytes.Contains(input, []byte("sudo -n"))
	direct := program == "sudo" && len(args) > 0 && args[0] == "-n"
	if t.SudoPassword == nil || (!script && !direct) {
		return run(program, args, input)
	}
	var output []byte
	err := t.SudoPassword(ctx, func(password []byte) error {
		if len(password) == 0 || len(password) > 32768 || bytes.ContainsAny(password, "\r\n\x00") {
			return errors.New("SESSION_CREDENTIAL_PASSWORD_FORMAT_UNSUPPORTED")
		}
		var framed []byte
		if script {
			framed = append(framed, []byte("set +ax\nunset _platform_sudo_password\nIFS= read -r _platform_sudo_password || exit 64\n")...)
		}
		framed = append(framed, password...)
		framed = append(framed, '\n')
		if script {
			framed = append(framed, executionSudoFunction...)
		}
		framed = append(framed, input...)
		defer func() {
			for i := range framed {
				framed[i] = 0
			}
		}()
		if direct {
			wrapper := "set +ax\nunset _platform_sudo_password\nIFS= read -r _platform_sudo_password || exit 64\n" + executionSudoFunction + "sudo \"$@\""
			args = append([]string{"-c", "'" + strings.ReplaceAll(wrapper, "'", "'\\''") + "'", "--"}, args...)
			program = "sh"
		}
		var err error
		output, err = run(program, args, framed)
		return err
	})
	return output, err
}
