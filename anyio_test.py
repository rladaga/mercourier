import anyio


async def productor(send_channel):
    for i in range(5):
        await send_channel.send(f"evento {i}")
    await send_channel.aclose()


async def consumidor(receive_channel):
    async with receive_channel:
        async for evento in receive_channel:
            print("Consumidor recibió:", evento)


async def main():
    send_channel, receive_channel = anyio.create_memory_object_stream()
    async with anyio.create_task_group() as tg:
        tg.start_soon(productor, send_channel)
        tg.start_soon(consumidor, receive_channel)


anyio.run(main)
