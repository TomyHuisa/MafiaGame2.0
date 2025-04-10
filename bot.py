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
        if num_jugadores < 1 or num_jugadores > 4:
            await ctx.send("La partida debe tener entre 1 y 4 jugadores.")
            return

        partidas[ctx.channel.id] = {
            "creador": ctx.author,
            "num_jugadores": num_jugadores,
            "jugadores": [],
            "bots": [],
            "fase": "esperando"
        }
        await ctx.send(f"Se ha creado una partida de Mafia para {num_jugadores} jugadores. Usa `!mafia unirme` para participar o `!mafia agregar_bot` para añadir bots.")

    elif accion == "unirme":
        if ctx.channel.id not in partidas:
            await ctx.send("No hay ninguna partida activa en este canal. Usa `!mafia crear <número>` para iniciar una.")
            return

        partida = partidas[ctx.channel.id]
        if ctx.author in partida["jugadores"]:
            await ctx.send("Ya estás en la partida.")
            return
        if len(partida["jugadores"]) + len(partida["bots"]) >= partida["num_jugadores"]:
            await ctx.send("La partida ya está completa.")
            return

        partida["jugadores"].append(ctx.author)
        await ctx.send(f"{ctx.author.display_name} se ha unido. Jugadores actuales: {len(partida['jugadores']) + len(partida['bots'])}/{partida['num_jugadores']}")

        if len(partida["jugadores"]) + len(partida["bots"]) == partida["num_jugadores"]:
            await ctx.send("¡La partida está lista! Asignando roles...")
            await asignar_roles(ctx.channel)

    elif accion == "agregar_bot":
        if ctx.channel.id not in partidas:
            await ctx.send("No hay ninguna partida activa en este canal.")
            return

        partida = partidas[ctx.channel.id]
        if len(partida["jugadores"]) + len(partida["bots"]) >= partida["num_jugadores"]:
            await ctx.send("La partida ya está completa.")
            return

        bot_name = f"Bot_{len(partida['bots']) + 1}"
        partida["bots"].append(bot_name)
        await ctx.send(f"{bot_name} se ha unido. Jugadores actuales: {len(partida['jugadores']) + len(partida['bots'])}/{partida['num_jugadores']}")

        if len(partida["jugadores"]) + len(partida["bots"]) == partida["num_jugadores"]:
            await ctx.send("¡La partida está lista! Asignando roles...")
            await asignar_roles(ctx.channel)

async def asignar_roles(channel):
    partida = partidas[channel.id]
    jugadores = partida["jugadores"] + partida["bots"]
    num_jugadores = len(jugadores)

    roles = ["Mafioso", "Doctor", "Detective"]
    roles += ["Ciudadano"] * (num_jugadores - len(roles))
    random.shuffle(roles)

    rol_asignado = {}
    mafiosos = []
    for jugador, rol in zip(jugadores, roles):
        rol_asignado[jugador] = rol
        if isinstance(jugador, discord.Member):
            try:
                await jugador.send(f"Tu rol es **{rol}**.")
            except:
                await channel.send(f"No pude enviar mensaje privado a {jugador.mention}. Asegúrate de que tienes los DMs activados.")
        if rol == "Mafioso":
            mafiosos.append(jugador)

    partida["roles"] = rol_asignado
    partida["mafiosos"] = mafiosos
    partida["fase"] = "noche"
    await channel.send("Los roles han sido asignados en secreto. La partida comienza... 🌙 ¡Es de noche!")

    await procesar_noche(channel)

async def verificar_fin_partida(channel):
    partida = partidas[channel.id]
    jugadores = partida["jugadores"] + partida["bots"]
    mafiosos = [j for j in jugadores if partida["roles"].get(j) == "Mafioso"]
    ciudadanos = len(jugadores) - len(mafiosos)

    if len(mafiosos) == 0:
        await channel.send("¡Los ciudadanos han ganado la partida! 🎉")
        del partidas[channel.id]
        return True
    elif len(mafiosos) >= ciudadanos:
        await channel.send("¡Los mafiosos han ganado la partida! 😈")
        del partidas[channel.id]
        return True
    return False

async def procesar_noche(channel):
    partida = partidas[channel.id]
    jugadores = partida["jugadores"] + partida["bots"]
    mafiosos = partida["mafiosos"]

    if any(isinstance(mafioso, str) for mafioso in mafiosos):
        victima = random.choice([j for j in jugadores if j not in mafiosos])
        await channel.send(f"Los mafiosos han elegido eliminar a {victima}.")
        jugadores.remove(victima)
        partida["jugadores"] = [j for j in jugadores if isinstance(j, discord.Member)]
        partida["bots"] = [j for j in jugadores if isinstance(j, str)]
    
    if await verificar_fin_partida(channel):
        return
    
    await channel.send("☀️ Amanece, ¡es hora de la votación!")
    await procesar_votacion(channel)

async def procesar_votacion(channel):
    await channel.send("¡Es momento de votar! Usa `!votar <nombre>` para eliminar a un jugador.")
    # Aquí se puede implementar la lógica de votación real.

# Iniciar el bot
bot.run(TOKEN)
