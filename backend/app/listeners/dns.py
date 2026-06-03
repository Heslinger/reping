import asyncio
from contextlib import suppress
from datetime import UTC, datetime

from dnslib import A, QTYPE, RR, DNSRecord

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.pingbacks import ingest_dns_pingback


class DNSPingbackProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        asyncio.create_task(self._handle_query(data, addr))

    async def _handle_query(self, data: bytes, addr: tuple[str, int]) -> None:
        settings = get_settings()
        try:
            request = DNSRecord.parse(data)
            query = request.q
            query_name = str(query.qname).strip(".").lower()
            record_type = QTYPE[query.qtype]

            async with AsyncSessionLocal() as session:
                await ingest_dns_pingback(
                    session,
                    query_name=query_name,
                    record_type=record_type,
                    source_ip=addr[0],
                    raw_event={
                        "source_port": addr[1],
                        "captured_at": datetime.now(UTC).isoformat(),
                    },
                )

            reply = request.reply()
            if record_type in {"A", "ANY"}:
                reply.add_answer(
                    RR(
                        rname=query.qname,
                        rtype=QTYPE.A,
                        rclass=1,
                        ttl=settings.dns_ttl_seconds,
                        rdata=A("127.0.0.1"),
                    )
                )
            self.transport.sendto(reply.pack(), addr)
        except Exception:
            with suppress(Exception):
                failure = DNSRecord.parse(data).reply()
                self.transport.sendto(failure.pack(), addr)


async def start_dns_listener() -> asyncio.DatagramTransport:
    settings = get_settings()
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        DNSPingbackProtocol,
        local_addr=(settings.dns_listen_host, settings.dns_listen_port),
    )
    return transport
