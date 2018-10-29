{
    "hostname": "myhost",
    "public_keys": [
        {
            "name": "mykey",
            "key": "ssh-rsa public_key"
        }],
    "network_data": {
      "links": [
          {
              "id": "eth0",
              "type": "phy",
              "ethernet_mac_address": "00:00:00:00:00:01"
          },
          {
              "id": "eth1",
              "type": "phy",
              "ethernet_mac_address": "00:00:00:00:00:02"
          }],
      "networks": [
          {
              "id": "management",
              "type": "ipv4",
              "link": "eth1",
              "ip_address": "192.168.0.100",
              "netmask": "255.255.255.0",
              "routes": [
                  {
                      "network": "0.0.0.0",
                      "netmask": "0.0.0.0",
                      "gateway": "192.168.0.1"
                  }]
          }]
    },
    "user_data": "A RANDOM STRING OF USER DATA",
    "misc_files": {"destination path": "base64 encoded file"}
}
