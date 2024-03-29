import discord
from discord import app_commands
from discord.ext import commands, tasks
import subprocess
import os
import docker
from mcstatus import JavaServer
from datetime import datetime

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
DISPLAY_IPV4_ADDRESS = os.environ.get("DISPLAY_IPV4_ADDRESS", default="None")
DISPLAY_IPV6_ADDRESS = os.environ.get("DISPLAY_IPV6_ADDRESS", default="None")

class ServerBot(commands.Bot):
    def __init__(self, command_prefix: str, intents: discord.Intents, docker_client: docker.DockerClient):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.docker_container = docker_client.containers
        self.counter = 0

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
        self.check_minecraft_player_count.start()

    @tasks.loop(minutes=1)
    async def check_minecraft_player_count(self):
        self.counter += 1

        mc_container = self.docker_container.get("minecraft-java")

        if mc_container.status == "exited" or mc_container.status == "paused":
            mc_server.set_mc_server(None)

            await client.change_presence(
                status = discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.watching, name="Minecraft Server | Offline")
            )
            
            return
        else:
            mc_server.set_mc_server(JavaServer.lookup(MINECRAFT_SERVER_ADDRESS))

            mc_server_player_count = mc_server.get_mc_server().status().players.online

            await client.change_presence(
                status = discord.Status.online, 
                activity=discord.Activity(type=discord.ActivityType.watching, name=f"Minecraft Server | Online | {mc_server_player_count} / {mc_server.get_mc_server().status().players.max}")
            )

            channel = self.get_channel(int(NOTIFICATION_CHANNEL_ID))
            if self.counter > 30 and mc_server_player_count <= 0:
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

                self.counter = 0
        
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
        embed.add_field(name="IPv4 Address", value=DISPLAY_IPV4_ADDRESS, inline=True)
        embed.add_field(name="IPv6 Address", value=DISPLAY_IPV6_ADDRESS, inline=True)
        embed.add_field(name="Container ID", value=mc_container.id, inline=False)

        await ctx.send(embeds=[embed])
    except docker.errors.APIError as e:
        embed = discord.Embed(title="Error", color=discord.Color.red(), description=e)
        await ctx.send(embeds=[embed])
    except:
        embed = discord.Embed(title="Error", color=discord.Color.red(), description="An error has occured")
        await ctx.send(embeds=[embed])
                  
@client.command()
async def mc_status(ctx: commands.Context):
    if mc_server.get_mc_server() != None:
        embed = discord.Embed(title="Server Status", color=discord.Color.green(), description=f"Minecraft server is currently **online**")

        embed.add_field(name="IPv4 Address", value=DISPLAY_IPV4_ADDRESS, inline=True)
        embed.add_field(name="IPv6 Address", value=DISPLAY_IPV6_ADDRESS, inline=True)
        
        await ctx.send(embeds=[embed])     
    else:
        embed = discord.Embed(title="Server Status", color=discord.Color.red(), description=f"Minecraft server is currently **offline**")
        await ctx.send(embeds=[embed])     

if __name__ == "__main__":
    if DISCORD_TOKEN == None or NOTIFICATION_CHANNEL_ID == None or MINECRAFT_SERVER_ADDRESS == None or DISPLAY_IPV4_ADDRESS == None or DISPLAY_IPV6_ADDRESS == None:
        os.abort()

    client.run(DISCORD_TOKEN)