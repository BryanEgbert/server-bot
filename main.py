import discord
import subprocess
from discord.ext import commands, tasks
from mcstatus import JavaServer
import os
import docker
from discord import app_commands
from datetime import datetime
import time

class MCServer():
    def __init__(self):
        self.mc_server = None

    def set_mc_server(self, val) -> None:
        self.mc_server = val

    def get_mc_server(self):
        return self.mc_server

mc_server = MCServer()
DOCKER_CLIENT = docker.from_env()
NOTIFICATION_CHANNEL_ID = os.environ.get("NOTIFICATION_CHANNEL_ID")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
MINECRAFT_SERVER_ADDRESS = os.environ.get("MINECRAFT_SERVER_ADDRESS")
BOT_CLIENT_ID = os.environ.get("BOT_CLIENT_ID")

class ServerBot(commands.Bot):
    def __init__(self, command_prefix: str, intents: discord.Intents, docker_client: docker.DockerClient):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.docker_container = docker_client.containers

    async def on_ready(self) -> None:
        try:
            container = self.docker_container.get("minecraft-java")
            if container.status == "exited" or container.status == "paused":
                mc_server.set_mc_server(None)
            else:
                mc_server.set_mc_server(JavaServer.lookup(MINECRAFT_SERVER_ADDRESS))
        except docker.errors.NotFound:
            mc_server.set_mc_server(None)
        except docker.errors.APIError as e:
            print(f"Something is wrong: {e}")

        print(f'Server started sucessfully.')
    
    async def setup_hook(self) -> None:
        self.update_bot_activity().start()
        self.check_minecraft_player_count.start()

    @tasks.loop(minutes=1)
    async def update_bot_activity(self):
        await wait_until_ready()
        if mc_server.get_mc_server() == None:
            await client.change_presence(
                status = discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.watching, name="Minecraft Server | Offline")
            )
            return

        mc_server_player_count = mc_server.get_mc_server().status().players.online
        if mc_server_player_count > 0:
            await client.change_presence(
                status = discord.Status.online, 
                activity=discord.Activity(type=discord.ActivityType.watching, name=f"Minecraft Server | Online | {mc_server_player_count} / {mc_server.get_mc_server().status().players.max}")
            )

            return

    @tasks.loop(minutes=30)
    async def check_minecraft_player_count(self):
        if mc_server.get_mc_server() == None:
            return

        mc_server_player_count = mc_server.get_mc_server().status().players.online
        if mc_server_player_count > 0:
            return

        channel = self.get_channel(int(NOTIFICATION_CHANNEL_ID))
        try:

            mc_container = self.docker_container.get("minecraft-java")
            container = mc_container.stop()

            mc_server.set_mc_server(None)

            embed = discord.Embed(title="Server Update", color=discord.Color.red(), description="Minecraft server is now offline")
            await channel.send(embeds=[embed])
        except docker.errors.APIError as e:
            embed = discord.Embed(title="Error", color=discord.Color.red(), description="Error in stopping the minecraft server")
            embed.add_field(name="Stacktrace", value=e)

            await channel.send(embeds=[embed])
    
    @check_minecraft_player_count.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()

intents = discord.Intents.default()
intents.message_content = True

client = ServerBot("$", intents, docker_client=DOCKER_CLIENT)

@client.command()
async def start_mc(ctx: commands.Context):
    try:
        mc_container = DOCKER_CLIENT.containers.get("minecraft-java")
        container = mc_container.start()

        mc_server.set_mc_server(JavaServer.lookup(os.environ.get("MINECRAFT_SERVER_ADDRESS")))

        embed = discord.Embed(title="Server Update", color=discord.Color.green(), description=f"Minecraft server started successfully. Server will auto close if there is no players online in the server")
        embed.add_field(name="Container ID", value=mc_container.id)

        await ctx.send(embeds=[embed])
    except docker.errors.APIError as e:
        embed = discord.Embed(title="Error", color=discord.Color.red(), description=e)
        await ctx.send(embeds=[embed])
                  
@client.command()
async def mc_status(ctx: commands.Context):
    if mc_server.get_mc_server() != None:
        embed = discord.Embed(title="Server Status", color=discord.Color.green(), description=f"Minecraft server is currently **online**")
        await ctx.send(embeds=[embed])     
    else:
        embed = discord.Embed(title="Server Status", color=discord.Color.red(), description=f"Minecraft server is currently **offline**")
        await ctx.send(embeds=[embed])     

if __name__ == "__main__":
    if DISCORD_TOKEN == None or NOTIFICATION_CHANNEL_ID == None or MINECRAFT_SERVER_ADDRESS == None or BOT_CLIENT_ID == None:
        os.abort()

    client.run(DISCORD_TOKEN)