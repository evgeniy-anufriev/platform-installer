// QA-only container probe. Build with CGO_ENABLED=0 and a scratch image.
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"slices"
	"time"
)

func main() {
	name, address := os.Getenv("QA_DNS_NAME"), os.Getenv("QA_DNS_ADDRESS")
	if name == "" || net.ParseIP(address) == nil {
		fmt.Fprintln(os.Stderr, "CONTAINER_DNS_PROBE_INPUT_INVALID")
		os.Exit(2)
	}
	resolver := &net.Resolver{PreferGo: true}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	addresses, err := resolver.LookupHost(ctx, name)
	if err != nil || !slices.Contains(addresses, address) {
		fmt.Fprintln(os.Stderr, "CONTAINER_DNS_UNAVAILABLE")
		os.Exit(1)
	}
	fmt.Println("CONTAINER_DNS_RESPONDED")
}
