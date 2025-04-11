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
        if num_jugadores < 2:
            await ctx.send("La partida debe tener más de 2 jugadores.")
            return

        partidas[ctx.channel.id] = {
            "creador": ctx.author,
            "num_jugadores": num_jugadores,
            "jugadores": [],
            "fase": "esperando",
            "votos": {},
            "roles": {},
            "mafiosos": [],
            "objetivo_mafia": None,
            "objetivo_doctor": None,
            "objetivo_detective": None,
            "acciones_noche": set()
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
        if isinstance(jugador, discord.Member):
            try:
                await jugador.send(f"Tu rol es **{rol}**. Usa comandos por aquí durante la noche si tienes un rol activo.")
            except:
                await channel.send(f"No pude enviar mensaje privado a {jugador.mention}. Asegúrate de que tienes los DMs activados.")
        if rol == "Mafioso":
            mafiosos.append(jugador)

    partida["roles"] = rol_asignado
    partida["mafiosos"] = mafiosos
    partida["fase"] = "día"
    await channel.send("Los roles han sido asignados en secreto. La partida comienza... ☀️ ¡Es de día!")
    await procesar_votacion(channel)

@bot.command()
async def votar(ctx, jugador: str):
    if ctx.channel.id not in partidas:
        await ctx.send("No hay ninguna partida activa en este canal.")
        return

    partida = partidas[ctx.channel.id]
    if ctx.author not in partida["jugadores"]:
        await ctx.send("No estás en la partida actual.")
        return

    jugador_obj = next((j for j in partida["jugadores"] if j.display_name.lower() == jugador.lower()), None)
    if not jugador_obj:
        await ctx.send("Ese jugador no está en la partida.")
        return

    partida["votos"][ctx.author] = jugador_obj.display_name
    await ctx.send(f"{ctx.author.display_name} ha votado por eliminar a {jugador_obj.display_name}.")

async def procesar_votacion(channel):
    partida = partidas[channel.id]
    votos = {}
    for votante, votado in partida["votos"].items():
        votos[votado] = votos.get(votado, 0) + 1

    if not votos:
        await channel.send("No hubo suficientes votos en esta ronda. Continúa la partida...")
        partida["fase"] = "noche"
        await procesar_noche(channel)
        return

    eliminado = max(votos, key=votos.get)
    jugador_eliminado = next((j for j in partida["jugadores"] if j.display_name == eliminado), None)

    if jugador_eliminado:
        await channel.send(f"{jugador_eliminado.display_name} ha sido eliminado. Era {partida['roles'].get(jugador_eliminado, 'un desconocido')}.")
        partida["jugadores"].remove(jugador_eliminado)
    else:
        await channel.send(f"No se encontró al jugador {eliminado}. Se omite la eliminación.")

    partida["votos"] = {}
    mafiosos_vivos = sum(1 for p in partida["mafiosos"] if p in partida["jugadores"])
    ciudadanos_vivos = len(partida["jugadores"]) - mafiosos_vivos
    if mafiosos_vivos == 0:
        await channel.send("Los ciudadanos han ganado. 🎉")
        del partidas[channel.id]
    elif mafiosos_vivos >= ciudadanos_vivos:
        await channel.send("Los mafiosos han tomado el control. 😈 La mafia gana.")
        del partidas[channel.id]
    else:
        partida["fase"] = "noche"
        await channel.send("🌙 La noche cae nuevamente...")
        await enviar_acciones_noche(channel)

async def enviar_acciones_noche(channel):
    partida = partidas[channel.id]
    partida["acciones_noche"] = set()
    partida["objetivo_mafia"] = None
    partida["objetivo_doctor"] = None
    partida["objetivo_detective"] = None

    for jugador in partida["jugadores"]:
        rol = partida["roles"].get(jugador)
        try:
            if rol == "Mafioso":
                await jugador.send("Es de noche. Usa `!matar <nombre>` para elegir a tu víctima.")
            elif rol == "Doctor":
                await jugador.send("Es de noche. Usa `!curar <nombre>` para proteger a un jugador.")
            elif rol == "Detective":
                await jugador.send("Es de noche. Usa `!investigar <nombre>` para investigar a un jugador.")
        except:
            await channel.send(f"No pude contactar por DM a {jugador.display_name} para las acciones nocturnas.")

@bot.command()
async def matar(ctx, nombre: str):
    await procesar_accion_noche(ctx, nombre, "Mafioso")

@bot.command()
async def curar(ctx, nombre: str):
    await procesar_accion_noche(ctx, nombre, "Doctor")

@bot.command()
async def investigar(ctx, nombre: str):
    await procesar_accion_noche(ctx, nombre, "Detective")

def obtener_jugador_por_nombre(nombre, jugadores):
    return next((j for j in jugadores if j.display_name.lower() == nombre.lower()), None)

async def procesar_accion_noche(ctx, nombre, rol_esperado):
    for partida in partidas.values():
        if ctx.author in partida["jugadores"]:
            break
    else:
        return await ctx.author.send("No estás en ninguna partida activa.")

    rol_real = partida["roles"].get(ctx.author)
    if rol_real != rol_esperado:
        return await ctx.author.send(f"No puedes usar este comando porque no eres {rol_esperado}.")

    if partida["fase"] != "noche":
        return await ctx.author.send("Este comando solo puede usarse durante la noche.")

    objetivo = obtener_jugador_por_nombre(nombre, partida["jugadores"])
    if not objetivo:
        return await ctx.author.send("El jugador no está en la partida o el nombre está mal escrito.")

    if rol_esperado == "Mafioso":
        partida["objetivo_mafia"] = objetivo
    elif rol_esperado == "Doctor":
        partida["objetivo_doctor"] = objetivo
    elif rol_esperado == "Detective":
        resultado = "Mafioso" if partida["roles"].get(objetivo) == "Mafioso" else "Inocente"
        await ctx.author.send(f"Resultado de la investigación: {objetivo.display_name} es {resultado}.")
    partida["acciones_noche"].add(ctx.author)

    if len(partida["acciones_noche"]) >= len([j for j in partida["jugadores"] if partida["roles"].get(j) in ["Mafioso", "Doctor", "Detective"]]):
        await procesar_noche(channel=ctx.channel)

async def procesar_noche(channel):
    partida = partidas[channel.id]
    victima = partida["objetivo_mafia"]
    salvado = partida["objetivo_doctor"]

    if victima and victima != salvado:
        partida["jugadores"].remove(victima)
        await channel.send(f"🌅 Amanece y se descubre que {victima.display_name} ha sido asesinado durante la noche.")
    elif victima:
        await channel.send(f"🌅 Amanece, y {victima.display_name} fue atacado, pero alguien lo salvó.")
    else:
        await channel.send("🌅 Amanece, pero no hubo asesinatos esta noche.")

    mafiosos_vivos = sum(1 for p in partida["mafiosos"] if p in partida["jugadores"])
    ciudadanos_vivos = len(partida["jugadores"]) - mafiosos_vivos
    if mafiosos_vivos == 0:
        await channel.send("Los ciudadanos han ganado. 🎉")
        del partidas[channel.id]
    elif mafiosos_vivos >= ciudadanos_vivos:
        await channel.send("Los mafiosos han tomado el control. 😈 La mafia gana.")
        del partidas[channel.id]
    else:
        partida["fase"] = "día"
        partida["votos"] = {}
        await channel.send("☀️ ¡Es de día nuevamente! Discutan entre ustedes y voten con `!votar <nombre>`.")
        await procesar_votacion(channel)

bot.run(TOKEN)