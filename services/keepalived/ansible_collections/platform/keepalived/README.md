# platform.keepalived

NET-02 package for deployment-owned IPv4 virtual-address ownership through
unicast VRRP. One Keepalived deployment renders one VRRP instance and one
shared election domain; all of its virtual addresses move together. The
package materializes, but does not activate, the future HAProxy helper.
