import json
import os
import requests
from pathlib import Path
from dataclasses import dataclass

TEST_ID = "1c4ffcd5-c7b7-44f6-9769-23e6d5e23799"

RPC_URLS = {
    "allthatnode_free": "https://sui-mainnet-rpc.allthatnode.com",
    "blastapi_free": "https://sui-mainnet.public.blastapi.io",
    "blockvision_free": "https://sui-mainnet-endpoint.blockvision.org",
    "chainode_free": "https://sui1mainnet-rpc.chainode.tech",
    "cosmostation_ca_free": "https://sui-mainnet-ca-2.cosmostation.io",
    "cosmostation_eu_free": "https://sui-mainnet-eu-4.cosmostation.io",
    "cosmostation_us_free": "https://sui-mainnet-us-2.cosmostation.io",
    "mysten_labs_free": "https://fullnode.mainnet.sui.io",
    "shimami_paid": "https://api.shinami.com/node/v1/sui_mainnet_840262afcbd4d60b3d497b9d99fd89c3",
    "suiet_free": "https://mainnet.suiet.app",
    "suiscan_free": "https://rpc-mainnet.suiscan.xyz",
}

FLY_REGIONS = [
    "ams",
    "iad",
    "atl",
    "bog",
    "bos",
    "otp",
    "ord",
    "dfw",
    "den",
    "eze",
    "fra",
    "gdl",
    "hkg",
    "jnb",
    "lhr",
    "lax",
    "mad",
    "mia",
    "yul",
    "bom",
    "cdg",
    "phx",
    "qro",
    "gig",
    "sjc",
    "scl",
    "gru",
    "sea",
    "ewr",
    "sin",
    "arn",
    "syd",
    "nrt",
    "yyz",
    "waw",
]


@dataclass
class RpcEndpoint:
    name: str
    url: str


def get_rpc_order_for_region(
    region_code: str,
):
    r = requests.get(f"https://suinfra.io/api/v1/rpc/{TEST_ID}/")
    data = r.json()["data"]

    rpcs: list[RpcEndpoint] = []
    for rpc in data[region_code]:
        # Skip paid endpoints.
        if rpc["rpc_name"].endswith("_paid"):
            continue
        # Skip TritonOne.
        if rpc["rpc_name"].startswith("triton_one"):
            continue

        if rpc["rpc_name"].endswith("_free"):
            rpcs.append(
                RpcEndpoint(
                    name=rpc["rpc_name"].replace("_free", ""),
                    url=rpc["rpc_url"],
                )
            )

    return rpcs


def generate_rpc_pool_backend_config(
    rpcs: list[RpcEndpoint],
):
    servers: list[str] = []
    starting_port = 9000
    for index, rpc in enumerate(rpcs):
        server_line = f"\tserver {rpc.name}_backend 127.0.0.1:{starting_port + index} check"  # fmt: skip
        if index > 2:
            server_line = f"{server_line} backup"
        servers.append(server_line)

    config_text = (
        "backend rpc_pool_backend",
        "\toption httpchk",
        "\tbalance leastconn",
        "\tdefault-server inter 30s fall 5 rise 3",
        """\thttp-check send meth POST uri / ver HTTP/1.1 hdr Content-Type application/json body '{"jsonrpc": "2.0", "method": "suix_getReferenceGasPrice", "params": [], "id":1}'""",
        "\n".join(servers),
    )

    return "\n".join(config_text)


def generate_rpc_backend_configs(
    rpcs: list[RpcEndpoint],
):
    backends: list[str] = []
    for rpc in rpcs:
        config_text = (
            f"backend {rpc.name}_backend",
            "\toption httpchk",
            "\tdefault-server inter 30s fall 5 rise 3",
            f"\thttp-check connect port 443 ssl sni {rpc.url.replace('https://', '')}",
            f"""\thttp-check send meth POST uri / ver HTTP/1.1 hdr Content-Type application/json hdr Host {rpc.url.replace('https://', '')} body '{{"jsonrpc": "2.0", "method": "suix_getReferenceGasPrice", "params": [], "id":1}}'""",
            "\thttp-check expect status 200",
            "\thttp-request set-header Content-Type application/json",
            f"\thttp-request set-header Host {rpc.url.replace('https://', '')}",
            "\thttp-response set-header X-Provider %s",
            f"\tserver {rpc.url.replace('https://', '')} {rpc.url.replace('https://', '')}:443 check ssl verify none check-sni {rpc.url.replace('https://', '')}",
        )
        backends.append("\n".join(config_text))

    return "\n\n".join(backends)


def generate_rpc_proxy_configs(
    rpcs: list[RpcEndpoint],
):
    proxies: list[str] = []
    starting_port = 9000
    for index, rpc in enumerate(rpcs):
        proxies.append(
            "\n".join(
                (
                    f"frontend {rpc.name}_proxy",
                    f"\tbind *:{starting_port + index}",
                    "\toption http-keep-alive",
                    f"\tdefault_backend {rpc.name}_backend",
                )
            )
        )

    return "\n\n".join(proxies)


os.makedirs("./region_configs", exist_ok=True)

for region_code in FLY_REGIONS:
    backends: list[str] = []
    print(f"Generating config for {region_code}...")
    rpcs = get_rpc_order_for_region(region_code)
    proxies = generate_rpc_proxy_configs(rpcs)
    pool_backend = generate_rpc_pool_backend_config(rpcs)
    rpc_backends = generate_rpc_backend_configs(rpcs)
    print(rpc_backends)

    with open("./haproxy.cfg", "r+") as f:
        data = f.read()
        data = data.replace(
            "<DYNAMIC_CONFIG>",
            "\n\n".join(
                (
                    proxies,
                    pool_backend,
                    rpc_backends,
                )
            ),
        )

    with open(f"./region_configs/haproxy_{region_code}.cfg", "w+") as f:
        f.write(f"{data}")

print("Done!")
