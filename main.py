import discord
import subprocess
from discord.ext import commands, tasks
from mcstatus import JavaServer
import os
import docker


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

class ServerBot(commands.Bot):
    def __init__(self, command_prefix: str, intents: discord.Intents, docker_client: docker.DockerClient):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.docker_container = docker_client.containers

    async def on_ready(self) -> None:
        try:
            container = self.docker_container.get("minecraft-java")
            mc_server.set_mc_server(JavaServer.lookup(MINECRAFT_SERVER_ADDRESS))
        except docker.errors.NotFound:
            mc_server.set_mc_server(None)
        except docker.errors.APIError as e:
            print(f"Something is wrong: {e}")

        print(f'Server started sucessfully.')
    
    async def setup_hook(self) -> None:
        self.check_minecraft_player_count.start()

    @tasks.loop(minutes=5)
    async def check_minecraft_player_count(self):
        if mc_server.get_mc_server() == None:
            return

        if mc_server.get_mc_server().status().players.online > 0:
            return

        # process = subprocess.run(f"echo {password} | sudo -S docker stop minecraft-java", text=True, shell=True, stderr=True)
        try:
            channel = self.get_channel(os.environ.get())

            mc_container = self.docker_container.get("minecraft-java")
            container = mc_container.stop()

            mc_server.set_mc_server(None)

            await channel.send("Minecraft server is now offline")
        except docker.errors.APIError:
            await ctx.send(f"Something's wrong when stopping the minecraft server")
    
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

        embed = discord.Embed(title="Server Update", color=discord.Color.green(), description=f"Minecraft server started successfully")
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
    if DISCORD_TOKEN == None or NOTIFICATION_CHANNEL_ID == None or MINECRAFT_SERVER_ADDRESS == None:
        os.abort()

    client.run(DISCORD_TOKEN)