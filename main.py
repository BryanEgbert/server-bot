import discord
import subprocess
from discord.ext import commands, tasks
from mcstatus import JavaServer
import os
import docker

mc_server = None
docker_client = docker.from_env()

class ServerBot(commands.Bot):
    def __init__(self, command_prefix: str, intents: discord.Intents, docker_client: docker.DockerClient):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.docker_container = docker_client.containers

    async def on_ready(self) -> None:
        try:
            container = self.docker_container.get("minecraft-java")
            mc_server = JavaServer.lookup(os.environ.get("MINECRAFT_SERVER_ADDRESS"))
        except docker.errors.NotFound:
            mc_server = None
        except docker.errors.APIError:
            print("Something is wrong")

        print(f'Server started sucessfully.')
    
    async def setup_hook(self) -> None:
        self.check_minecraft_player_count.start()

    @tasks.loop(minutes=5)
    async def check_minecraft_player_count(self):
        global mc_server
        if mc_server == None:
            return

        if mc_server.players.online > 0:
            return

        # process = subprocess.run(f"echo {password} | sudo -S docker stop minecraft-java", text=True, shell=True, stderr=True)
        try:
            mc_container = self.docker_container.get("minecraft-java")
            container = mc_container.stop()

            mc_server = None

            await ctx.send(f"Minecraft server stopped: {container.id}")
        except docker.errors.APIError:
            await ctx.send(f"Something's wrong when stopping the minecraft server")
        
        # if process.returncode == 0:
        #     await ctx.send("Minecraft server stopped")
        # else:
        #     await ctx.send(f"Something wrong when stopping the minecraft server, trace log:\n{process.stderr}")

# client = commands.Bot(command_prefix=command_prefix, intents=intents)
intents = discord.Intents.default()
intents.message_content = True

client = ServerBot("$", intents, docker_client=docker_client)

@client.command()
async def start_mc(ctx: commands.Context):
    try:
        mc_container = docker_client.containers.get("minecraft-java")
        container = mc_container.start()

        mc_server = JavaServer.lookup(os.environ.get("MINECRAFT_SERVER_ADDRESS"))

        await ctx.send(f"Minecraft server started successfully: {container.id}")
    except docker.errors.APIError:
        await ctx.send("error when starting the minecraft server")

    # password = os.environ.get("PASSWORD")


    # if password != None:
        # process = subprocess.run(f"echo {password} | sudo -S docker start minecraft-java", text=True, shell=True, stderr=True)
        # if process.returncode == 0:
        #     if mc_server_started:
        #         await ctx.send("Minecraft server is already online")
        #     else: 
        #         mc_server_started = True
        #         mc_server = JavaServer.lookup(os.environ.get("MINECRAFT_SERVER_ADDRESS"))

        #         await ctx.send("Minecraft server started successfully.\nI will check the player count of the minecraft server every 5 minutes, server will automatically stop if there are no players in the server")
        # else:
        #     await ctx.send(f"Something wrong when starting the minecraft server, trace log:\n{process.stderr}")  
        

    # await ctx.send("You haven't set the PASSWORD environment variable")
                  

@client.command()
async def mc_status(ctx: commands.Context):
    if mc_server != None:
        await ctx.send(f"Minecraft server is currently online")     
    else:
        await ctx.send(f"Minecraft server is currently offline")     

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

if DISCORD_TOKEN == None:
    os.abort()

client.run(DISCORD_TOKEN)