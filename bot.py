import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import random

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Configurar Intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

# Configurar el bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Almacenar partidas
partidas = {}

@bot.event
async def on_ready():
    print(f"{bot.user.name} está en línea y listo para jugar Mafia.")

# Comando para crear una partida
@bot.command()
async def mafia(ctx, accion: str, *args):
    if accion == "crear":
        if ctx.channel.id in partidas:
            await ctx.send("Ya hay una partida en curso en este canal.")
            return

        if not args or not args[0].isdigit():
            await ctx.send("Debes especificar un número de jugadores. Ejemplo: `!mafia crear 6`")
            return

        num_jugadores = int(args[0])
        if num_jugadores < 1:
            await ctx.send("La partida debe tener al menos 1 a 4 jugadores.")
            return

        partidas[ctx.channel.id] = {
            "creador": ctx.author,
            "num_jugadores": num_jugadores,
            "jugadores": [],
            "fase": "esperando"
        }
        await ctx.send(f"Se ha creado una partida de Mafia para {num_jugadores} jugadores. Usa `!mafia unirme` para participar.")

    elif accion == "unirme":
        if ctx.channel.id not in partidas:
            await ctx.send("No hay ninguna partida activa en este canal. Usa `!mafia crear <número>` para iniciar una.")
            return

        partida = partidas[ctx.channel.id]
        if ctx.author in partida["jugadores"]:
            await ctx.send("Ya estás en la partida.")
            return
        if len(partida["jugadores"]) >= partida["num_jugadores"]:
            await ctx.send("La partida ya está completa.")
            return

        partida["jugadores"].append(ctx.author)
        await ctx.send(f"{ctx.author.display_name} se ha unido. Jugadores actuales: {len(partida['jugadores'])}/{partida['num_jugadores']}")

        if len(partida["jugadores"]) == partida["num_jugadores"]:
            await ctx.send("¡La partida está lista! Asignando roles...")
            await asignar_roles(ctx.channel)

async def asignar_roles(channel):
    partida = partidas[channel.id]
    jugadores = partida["jugadores"]
    num_jugadores = len(jugadores)

    roles = ["Mafioso", "Doctor", "Detective"]
    roles += ["Ciudadano"] * (num_jugadores - len(roles))
    random.shuffle(roles)

    rol_asignado = {}
    mafiosos = []
    for jugador, rol in zip(jugadores, roles):
        rol_asignado[jugador] = rol
        try:
            await jugador.send(f"Tu rol es **{rol}**.")
        except:
            await channel.send(f"No pude enviar mensaje privado a {jugador.mention}. Asegúrate de que tienes los DMs activados.")
        if rol == "Mafioso":
            mafiosos.append(jugador)

    partida["roles"] = rol_asignado
    partida["mafiosos"] = mafiosos
    partida["fase"] = "noche"
    await channel.send("Los roles han sido asignados en secreto. La partida comienza... 🌕 ¡Es de noche!")
    await enviar_instrucciones_mafiosos(mafiosos)

async def enviar_instrucciones_mafiosos(mafiosos):
    for mafioso in mafiosos:
        try:
            await mafioso.send("Es de noche. Usa `!matar <nombre>` en este chat privado para elegir a una víctima.")
        except:
            print(f"No pude enviar DM a {mafioso.display_name}.")

@bot.command()
async def matar(ctx, jugador: discord.Member):
    autor = ctx.author
    partida = next((p for p in partidas.values() if autor in p.get("mafiosos", [])), None)
    if not partida:
        await ctx.send("No estás en una partida activa o no eres mafioso.")
        return

    if jugador not in partida["jugadores"]:
        await ctx.send("Ese jugador no está en la partida.")
        return

    if "victima" in partida:
        await ctx.send("Ya se ha seleccionado una víctima esta noche.")
        return

    partida["victima"] = jugador
    await ctx.send(f"Has elegido eliminar a {jugador.display_name}. Se procesará al amanecer.")

# Iniciar el bot
bot.run(TOKEN)
