"""A minimal local TCP listener standing in for the real E4360A units during
development/demo. It does not speak SCPI or anything else — it only accepts
the TCP handshake so the poller's genuine `check_reachable` probe (a real
`socket.create_connection`, see driver.py) has something real to connect to
by default. Nothing about the reachability check is faked: a connection
either succeeds or it doesn't. Point a unit's IP/port at your actual
instrument (Configuration → Simulator Units) once you're running the app on
a host with LAN access to it, and this stub becomes irrelevant to that unit.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        await reader.read(256)
    except Exception:
        pass
    finally:
        writer.close()


async def start_stub_listeners(ports: list[int], host: str = "127.0.0.1") -> list[asyncio.AbstractServer]:
    servers = []
    for port in ports:
        try:
            server = await asyncio.start_server(_handle, host, port)
            servers.append(server)
        except OSError:
            logger.warning("stub instrument listener on %s:%s could not start (port already in use?)", host, port)
    return servers
