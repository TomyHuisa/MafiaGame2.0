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
            await ctx.send("La partida debe tener más de 1 jugador o varios jugadores.")
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
                await jugador.send(f"Tu rol es **{rol}**.")
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

    partida["votos"][ctx.author] = jugador
    await ctx.send(f"{ctx.author.display_name} ha votado por eliminar a {jugador}.")

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
    await channel.send(f"{eliminado} ha sido eliminado. Era {partida['roles'].get(eliminado, 'un desconocido')}.")

    for jugador in partida["jugadores"]:
        if jugador.display_name == eliminado:
            partida["jugadores"].remove(jugador)
            break

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
        await procesar_noche(channel)

async def procesar_noche(channel):
    partida = partidas[channel.id]
    partida["objetivo_mafia"] = None
    partida["objetivo_doctor"] = None
    partida["objetivo_detective"] = None
    partida["acciones_noche"] = set()

    for jugador in partida["jugadores"]:
        rol = partida["roles"].get(jugador)
        try:
            if rol == "Mafioso":
                await jugador.send("Es de noche. Usa `!matar <nombre>` para decidir a quién eliminar.")
            elif rol == "Doctor":
                await jugador.send("Es de noche. Usa `!curar <nombre>` para proteger a alguien.")
            elif rol == "Detective":
                await jugador.send("Es de noche. Usa `!investigar <nombre>` para investigar a alguien.")
        except:
            await channel.send(f"No pude contactar por DM a {jugador.display_name} para la fase de noche.")

@bot.command()
async def matar(ctx, objetivo: str):
    for cid, partida in partidas.items():
        if ctx.author in partida["mafiosos"] and partida["fase"] == "noche":
            partida["objetivo_mafia"] = objetivo
            partida["acciones_noche"].add(ctx.author)
            await ctx.send(f"Has seleccionado a {objetivo} como objetivo. Esperando a los demás...")
            await verificar_acciones_noche(cid)
            return
    await ctx.send("No puedes usar este comando ahora.")

@bot.command()
async def curar(ctx, objetivo: str):
    for cid, partida in partidas.items():
        if partida["roles"].get(ctx.author) == "Doctor" and partida["fase"] == "noche":
            partida["objetivo_doctor"] = objetivo
            partida["acciones_noche"].add(ctx.author)
            await ctx.send(f"Has decidido proteger a {objetivo} esta noche.")
            await verificar_acciones_noche(cid)
            return
    await ctx.send("No puedes usar este comando ahora.")

@bot.command()
async def investigar(ctx, objetivo: str):
    for cid, partida in partidas.items():
        if partida["roles"].get(ctx.author) == "Detective" and partida["fase"] == "noche":
            jugador_investigado = next((j for j in partida["jugadores"] if j.display_name == objetivo), None)
            if jugador_investigado:
                es_mafioso = jugador_investigado in partida["mafiosos"]
                await ctx.author.send(f"{objetivo} {'ES' if es_mafioso else 'NO es'} un mafioso.")
            else:
                await ctx.author.send("Ese jugador no está en la partida.")
            partida["objetivo_detective"] = objetivo
            partida["acciones_noche"].add(ctx.author)
            await verificar_acciones_noche(cid)
            return
    await ctx.send("No puedes usar este comando ahora.")

async def verificar_acciones_noche(channel_id):
    partida = partidas[channel_id]
    acciones_requeridas = [j for j in partida["jugadores"] if partida["roles"].get(j) in ["Mafioso", "Doctor", "Detective"]]
    if all(j in partida["acciones_noche"] for j in acciones_requeridas):
        await finalizar_noche(channel_id)

async def finalizar_noche(channel_id):
    channel = bot.get_channel(channel_id)
    partida = partidas[channel_id]
    objetivo_mafia = partida.get("objetivo_mafia")
    objetivo_doctor = partida.get("objetivo_doctor")

    if objetivo_mafia and objetivo_mafia == objetivo_doctor:
        await channel.send(f"🌅 Amanece y {objetivo_mafia} fue atacado, pero fue salvado por el Doctor. 💉")
    elif objetivo_mafia:
        await channel.send(f"🌅 Amanece y {objetivo_mafia} ha sido eliminado durante la noche.")
        for jugador in partida["jugadores"]:
            if jugador.display_name == objetivo_mafia:
                partida["jugadores"].remove(jugador)
                break
    else:
        await channel.send("🌅 Amanece, pero nadie fue eliminado esta noche.")

    mafiosos_vivos = sum(1 for p in partida["mafiosos"] if p in partida["jugadores"])
    ciudadanos_vivos = len(partida["jugadores"]) - mafiosos_vivos

    if mafiosos_vivos == 0:
        await channel.send("Los ciudadanos han ganado. 🎉")
        del partidas[channel_id]
        return
    elif mafiosos_vivos >= ciudadanos_vivos:
        await channel.send("Los mafiosos han ganado. 😈")
        del partidas[channel_id]
        return

    partida["fase"] = "día"
    partida["votos"] = {}
    await channel.send("☀️ ¡Es de día! Los jugadores pueden discutir y votar usando `!votar <nombre>`")

bot.run(TOKEN)