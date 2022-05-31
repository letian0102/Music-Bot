from fileinput import filename
from xml.dom.minicompat import EmptyNodeList
import discord
from discord.ext import commands,tasks
import os
from dotenv import load_dotenv
import youtube_dl
import asyncio
import random
from youtube_dl import YoutubeDL
import yt_dlp

load_dotenv()

youtube_dl.utils.bug_reports_message = lambda: 'youtubedl bugs'

# Get the API token from the .env file.
DISCORD_TOKEN = os.getenv("discord_token")

intents = discord.Intents().all()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='~',intents=intents, help_command=None)

yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio',
    'restrictfilenames': True,
    'outtmpl': 'music_files/%(id)s.mp3',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}



ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

botDictionary = {}


@bot.event
async def on_ready():
    for guild in bot.guilds:
        botDictionary[guild] = {"q":[],"qn":[],"r_s":False,"curr":"","currS":"","time":0,"r_l":False}
    #print("Dictionary printed:"+str(botDictionary))



class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""
        

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        filename = data['title'] if stream else ytdl.prepare_filename(data)
        return filename

@bot.command(name='列表循环', help='播放歌曲', aliases=['repeat_list'])
async def repeat(ctx, url):
    server = ctx.message.guild
    botDictionary[server]["r_l"] = False
    if url in ["1","开","True","T"]:
        botDictionary[server]["r_l"] = True
        return await ctx.send("**列表循环已开**")
    else:
        botDictionary[server]["r_s"] = False
        return await ctx.send("**列表循环已关**")

@bot.command(name='单曲循环', help='播放歌曲', aliases=['repeat_single'])
async def repeat_single(ctx, url):
    server = ctx.message.guild
    botDictionary[server]["r_s"] = False
    if url in ["1","开","True","T"]:
        botDictionary[server]["r_s"] = True
        return await ctx.send("**单曲循环已开**")
    else:
        botDictionary[server]["r_s"] = False
        return await ctx.send("**单曲循环已关**")

@bot.event
async def check_queue(ctx):
    server = ctx.message.guild
    voice_members = list(
                filter(lambda x: not x.bot, ctx.voice_client.channel.members)
            )
    voice_client = ctx.message.guild.voice_client
    voice_client.stop()

    if botDictionary[server]["r_s"] == True and botDictionary[server]["curr"] != "": #单曲循环开+无单曲循环的歌
        await play_song(ctx, botDictionary[server]["curr"])
        return await ctx.send("**单曲循环：**"+ botDictionary[server]["currS"])
    elif len(botDictionary[server]["q"]) > 0: #单曲循环没开
        botDictionary[server]["curr"] = botDictionary[server]["q"].pop(0)
        botDictionary[server]["currS"] = botDictionary[server]["qn"].pop(0)
        if botDictionary[server]["r_l"] == True:
            botDictionary[server]["q"].append(botDictionary[server]["curr"])
            botDictionary[server]["qn"].append(botDictionary[server]["currS"])
        await play_song(ctx, botDictionary[server]["curr"])
        return await ctx.send("**正在播放：**"+botDictionary[server]["currS"])
    elif len(voice_members) < 1 or len(botDictionary[server]["q"]) == 0: #inactivity check
        while True:
            await asyncio.sleep(1)
            botDictionary[server]["time"] += 1
            if voice_client.is_playing() and not voice_client.is_paused():
                print("正在播放中")
                botDictionary[server]["time"] = 0
                break
            elif botDictionary[server]["time"] == 300 and voice_client.is_connected():
                print("退出")
                botDictionary[server]["time"] = 0
                await ctx.send("频道无人/歌单为空超时五分钟，自动退出。")
                return await leave(ctx)

#播放歌曲
@bot.command(name='播放', help='播放歌曲', aliases=['p','play'])
async def play(ctx,*,url):
    if not ctx.message.author.voice:
        await ctx.send("{} 并未在一个频道中".format(ctx.message.author.name))
        return
    voice_client = ctx.message.guild.voice_client

    if voice_client == None:
        channel = ctx.message.author.voice.channel
        await channel.connect()
    elif voice_client.is_connected() and ctx.guild.voice_client.channel != ctx.message.author.voice.channel:
        return await ctx.send("Bot已经在另一个频道内了！")

    try :
        server = ctx.message.guild
        voice_channel = server.voice_client
        voice_client = ctx.message.guild.voice_client
        #print(url)

        async with ctx.typing():
            filename = await YTDLSource.from_url(url, loop=bot.loop)
            #title = YTDLSource.title
            #print(title)
            #print(voice_client.is_playing())
            if filename in botDictionary[server]["q"]:
                return await ctx.send('**Queue内已含: ** {}'.format(url))
            botDictionary[server]["q"].append(filename)
            botDictionary[server]["qn"].append(url)

            if voice_client.is_playing(): #playing a song

                return await ctx.send('**已加入Queue: ** {}'.format(url))
            #print("准备play")
            await check_queue(ctx)
            #print("played")
    except:
        
        await ctx.send("无法播放。")

async def play_song(ctx, filename):
    server = ctx.message.guild
    voice_channel = server.voice_client
    voice_client = ctx.message.guild.voice_client
    #print("before play the song")
    voice_channel.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=filename), after=lambda error: bot.loop.create_task(check_queue(ctx)))    
    #print("after play the song")

#暂停歌曲
@bot.command(name='暂停', help='暂停歌曲', aliases=['pause'])
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        await voice_client.pause()
    else:
        await ctx.send("Bot并未在播放任何歌曲，无法暂停。")

#下首歌
@bot.command(name='跳过', help='跳过当前的歌曲', aliases=['s','skip'])
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    
    if not voice_client.is_playing():
        await ctx.send("Bot并未播放任何歌曲，无法跳过。")
    else:
        voice_client.stop()
        await ctx.send("**已跳过当前歌曲**")

#继续播放
@bot.command(name='继续', help='继续播放', aliases=['r','resume'])
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        await voice_client.resume()
    else:
        await ctx.send("Bot并未在播放任何的歌，请用“~播放”指令。")

@bot.command(name='删除', help='删除歌曲', aliases=['remove'])
async def remove(ctx, url):
    server = ctx.message.guild
    if url.isdigit() and int(url) < len(botDictionary[server]["q"]) and int(url) >= 0:
        del botDictionary[server]["q"][int(url)]
        temp = botDictionary[server]["qn"][int(url)]
        del botDictionary[server]["qn"][int(url)]
        await ctx.send("**已删除 **"+temp)
    elif len(botDictionary[server]["q"]) == 0:
        await ctx.send("歌单为空，请添加歌曲再删除。")
    else:
        await ctx.send("请输入正确的歌曲位置，详情请输入~list查看。")

#停止播放
@bot.command(name='停止', help='停止播放', aliases=['stop'])
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    server = ctx.message.guild
    if botDictionary[server]["q"] or botDictionary[server]["qn"]:
        botDictionary[server]["q"].clear()
        botDictionary[server]["qn"].clear()
    if voice_client.is_playing():
        voice_client.stop()
    else:
        await ctx.send("Bot并未在播放任何歌曲，无法停止。")

#进入频道
@bot.command(name='进入', help='让Bot进入频道', aliases=['join'])
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("{} 并未在一个频道中".format(ctx.message.author.name))
        return
    else:
        channel = ctx.message.author.voice.channel
    await channel.connect()

#离开频道
@bot.command(name='离开', help='让Bot离开频道', aliases=['leave'])
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    server = ctx.message.guild
    if voice_client.is_connected():
        botDictionary[server]["q"].clear()
        botDictionary[server]["qn"].clear()
        botDictionary[server]["r_s"] = False
        botDictionary[server]["curr"] = ""
        botDictionary[server]["currS"] = ""
        await voice_client.disconnect()
    else:
        await ctx.send("Bot并未在一个频道内，无法离开。")

#roll点数
@bot.command(name="roll", help="roll点数")
async def roll(ctx,url):
    if url.isdigit() == False:
        await ctx.send("无效数字，格式为：roll 数字")
    else:
        num = random.randrange(1, int(url))
        await ctx.send("你roll出了 **"+str(num)+"** !!")

@bot.command(name="列表", help="显示当前歌单", aliases=['list'])
async def queue(ctx):
    server = ctx.message.guild
    if botDictionary[server]["qn"] and len(botDictionary[server]["qn"]) > 0:
        string = "```"
        for i in range(len(botDictionary[server]["qn"])):
            string += str(i)+"："+botDictionary[server]["qn"][i]+"\n"
        string += "```"
        await ctx.send(string)
    else:
        await ctx.send("当前歌单为空")

#帮助
@bot.command(name="help", help="roll点数")
async def help(ctx):
    await ctx.send("```"+"~播放 [歌曲名]：播放下一首歌曲\n"+
    "~进入/join：进入你的房间\n"+
    "~离开/leave：离开你的房间\n"+
    "~暂停/pause：暂停当前歌曲\n"+
    "~继续/resume：继续播放当前歌曲\n"+
    "~跳过/skip：跳过当前歌曲\n"+
    "~roll [数字]：roll一个随机数字\n"+
    "~8ball [问题]：问Magic 8 Ball一个神奇的问题\n"+
    "~单曲循环/repeat_single [1/0]: 是否单曲循环当前播放歌曲\n"+
    "~列表循环/repeat_list [1/0]：是否列表循环\n"+
    "~删除/remove [位置]：删除在此位置的歌曲"+
    "```")

#magic 8ball
@bot.command(name="8ball", help="Magic 8 Ball!!!")
async def help(ctx,*,url):
    num = random.randrange(19)
    string = url+"\n"
    if num == 0:
        string += "**It is certain.**"
    elif num == 1:
        string += "**It is decidedly so.**"
    elif num == 2:
        string += "**Without a doubt.**"
    elif num == 3:
        string += "**Yes definitely.**"
    elif num == 4:
        string += "**You may rely on it.**"
    elif num == 5:
        string += "**As I see it, yes.**"
    elif num == 6:
        string += "**Most likely.**"
    elif num == 7:
        string += "**Outlook good.**"
    elif num == 8:
        string += "**Yes.**"
    elif num == 9:
        string += "**Signs point to yes.**"
    elif num == 10:
        string += "**Reply hazy, try again.**"
    elif num == 11:
        string += "**Ask again later.**"
    elif num == 12:
        string += "**Better not tell you now.**"
    elif num == 13:
        string += "**Cannot predict now.**"
    elif num == 14:
        string += "**Concentrate and ask again.**"
    elif num == 15:
        string += "**Don't count on it.**"
    elif num == 16:
        string += "**My reply is no.**"
    elif num == 17:
        string += "**My sources say no.**"
    elif num == 18:
        string += "**Outlook not so good.**"
    elif num == 19:
        string += "**Very doubtful.**"
    else:
        string += "ASK AGAIN!!!"
    await ctx.send(string)
    

if __name__ == "__main__" :
    bot.run(DISCORD_TOKEN)