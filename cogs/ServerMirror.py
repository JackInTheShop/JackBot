from discord.ext import commands
from os.path import exists
from io import BytesIO
import aiofiles
import discord
import asyncio
import json
import os

emotes = {
    'x': u'\u274c',
    'check': u'\u2705'
}

class ServerMirror(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.json_file = 'data/server_mirrors.json'
        if not exists(self.json_file):
            self._enslavable_guilds = []
            self._master_guilds = {}
            return

        with open(self.json_file,'r') as f:
            self._enslavable_guilds, tmp = json.loads(f.read())

        self._master_guilds = {}
        for i in tmp:
            self._master_guilds[int(i)] = {}
            for j in tmp[i]:
                self._master_guilds[int(i)][int(j)] = {'roles': {}, 'channels': {}}
                for k in tmp[i][j]:
                    for l in tmp[i][j][k]:
                        self._master_guilds[int(i)][int(j)][k][int(l)] = tmp[i][j][k][l]

    async def save(self):
        async with aiofiles.open(self.json_file,mode='w+') as f:
            await f.write(json.dumps([self._enslavable_guilds,self._master_guilds]))

    @commands.Cog.listener()
    async def on_guild_channel_delete(channel):
        if channel.guild.id not in self._master_guilds: return
        
        for i in self._master_guilds[channel.guild.id]:
            deleted_channel = self._master_guilds[channel.guild.id][i]['channel'].pop(channel.id)
            await self.bot.get_guild(i).get_channel(deleted_channel).delete()
        await self.save()

    @commands.Cog.listener()
    async def on_guild_channel_create(channel):
        if channel.guild.id not in self._master_guilds: return

        for i in self._master_guilds[before.guild.id]:

            slave_guild = self.bot.get_guild(i)

            overwrites = {}
            for k,v in channel.overwrites.items():
                overwrites[slave_guild.get_role(self._master_guilds[channel.guild.id][i]['roles'][k.id])] = v

            kwargs = {
                'name': channel.name,
                'overwrites': overwrites
            }

            if channel.type == discord.ChannelType.category:
                new_channel = await slave_guild.create_category_channel(**kwargs)
            else:
                category = None
                if cc.category_id in self._master_guilds[channel.guild.id][i]['channels']:
                    category = slave_guild.get_channel(self._master_guilds[channel.guild.id][i]['channels'][cc.category_id])

                kwargs['category'] = category
                kwargs['position'] = channel.position

            if channel.type == discord.ChannelType.text:
                kwargs['topic'] = channel.topic
                kwargs['nsfw'] = channel.nsfw
                kwargs['slowmode_delay'] = channel.slowmode_delay

                new_channel = await slave_guild.create_text_channel(**kwargs)

            elif channel.type == discord.ChannelType.voice:
                kwargs['bitrate'] = channel.bitrate
                kwargs['user_limit'] = channel.user_limit

                new_channel = await slave_guild.create_voice_channel(**kwargs)
            else:
                return

            self._master_guilds[channel.guild.id][i]['channels'][channel.id] = new_channel.id
            await self.save()

    @commands.Cog.listener()
    async def on_guild_channel_update(before,after):
        if before.guild.id not in self._master_guilds: return

        for i in self._master_guilds[before.guild.id]:

            slave_guild = self.bot.get_guild(i)
            slave_channel = slave_guild.get_channel(self._master_guilds[before.guild.id][i]['channels'][before.id])

            overwrites = {}
            for k,v in after.overwrites.items():
                overwrites[slave_guild.get_role(self._master_guilds[before.guild.id][i]['roles'][k.id])] = v

            kwargs = {
                'name': after.name,
                'position': after.position
            }

            if after.type == discord.ChannelType.category:

                for j in overwrites.items():
                    await slave_channel.set_permissions(j[0],overwrite=j[1])

            else:
                category = None
                if cc.category_id in self._master_guilds[before.guild.id][i]['channels']:
                    category = slave_guild.get_channel(self._master_guilds[before.guild.id][i]['channels'][cc.category_id])

                kwargs['overwrites'] = overwrites
                kwargs['category'] = category
                kwargs['sync_permissions'] = after.sync_permissions

            if after.type == discord.ChannelType.text:
                kwargs['topic'] = after.topic
                kwargs['nsfw'] = after.nsfw
                kwargs['slowmode_delay'] = after.slowmode_delay

            elif after.type == discord.ChannelType.voice:
                kwargs['bitrate'] = after.bitrate
                kwargs['user_limit'] = after.user_limit

            await slave_channel.edit(**kwargs)

    @commands.Cog.listener()
    async def on_guild_update(before,after):
        if before.id not in self._master_guilds: return

        icon = await after.icon_url_as(format='png',static_format='png').read()
        
        for i in self._master_guilds[after.id]:
            system_channel = None
            slave_guild = self.bot.get_guild(i)

            if after.system_channel is not None:
                system_channel = slave_guild.get_channel(self._master_guilds[after.id][slave_id]['channels'][after.system_channel.id])

            await slave_guild.edit(
                name=after.name,
                icon=icon,
                region=after.region,
                afk_channel=after.afk_channel,
                afk_timeout=after.afk_timeout,
                verification_level=after.verification_level,
                default_notifications=after.default_notifications,
                explicit_content_filter=after.explicit_content_filter,
                system_channel=system_channel,
                system_channel_flags=after.system_channel_flags
                )

    @commands.Cog.listener()
    async def on_guild_role_create(role):
        if role.guild.id not in self._master_guilds: return

        for i in self._master_guilds[role.guild.id]:
            new_role = await self.bot.get_guild(i).create_role(
                name=role.name,
                permissions=role.permissions,
                colour=role.colour,
                hoist=role.hoist,
                mentionable=role.mentionable)

            self._master_guilds[role.guild.id][i]['roles'][role.id] = new_role.id

        await self.save()

    @commands.Cog.listener()
    async def on_guild_role_delete(role):
        if role.guild.id not in self._master_guilds: return
        
        for i in self._master_guilds[role.guild.id]:
            deleted_role = self._master_guilds[role.guild.id][i]['roles'].pop(role.id)
            await self.bot.get_guild(i).get_role(deleted_role).delete()

        await self.save()

    @commands.Cog.listener()
    async def on_guild_role_update(before,after):
        if before.guild.id not in self._master_guilds: return

        for i in self._master_guilds[before.guild.id]:
            slave_role = self.bot.get_guild(i).get_role(self._master_guilds[before.guild.id][i]['roles'][before.id])
            await slave_role.edit(
                name=after.name,
                permissions=after.permissions,
                colour=after.colour,
                hoist=after.hoist,
                mentionable=after.mentionable,
                position=after.position
                )

    @commands.Cog.listener()
    async def on_member_ban(guild,user):
        if guild.id not in self._master_guilds: return

        for i in self._master_guilds[guild.id]:
             await self.bot.get_guild(i).ban(user)

    @commands.Cog.listener()
    async def on_member_unban(guild,user):
        if guild.id not in self._master_guilds: return

        reason = await guild.fetch_ban(user)[1]
        for i in self._master_guilds[guild.id]:
             await self.bot.get_guild(i).unban(user,reason=reason)

    @commands.Cog.listener()
    async def on_message(self,msg):
        if msg.guild.id not in self._master_guilds: return
        if msg.type != discord.MessageType.default: return
        if msg.author.bot: return

        avatar = await msg.author.avatar_url_as(format='png',static_format='png',size=256).read()
        files = []
        if msg.attachments:
            for i in msg.attachments:
                tmp = BytesIO()
                await i.save(tmp)
                files.append(discord.File(tmp,filename=i.filename))
        else:
            files = None

        for i in self._master_guilds[msg.guild.id]:
            channel = self.bot.get_guild(i).get_channel(self._master_guilds[msg.guild.id][i]['channels'][msg.channel.id])
            new_webhook = await channel.create_webhook(name=msg.author.name,avatar=avatar)
            await new_webhook.send(msg.content,files=files)
            await new_webhook.delete()

    @commands.command()
    async def mirror(self,ctx,slave_id: int):
        print('Mirror Request - '\
            'Requester: {} (ID: {}) '\
            'Master: {} (ID: {}) '\
            'Slave ID: {}'.format(
            ctx.author,
            ctx.author.id,
            ctx.guild,
            ctx.guild.id,
            slave_id))

        if ctx.guild.id in self._master_guilds and slave_id in self._master_guilds[ctx.guild.id]:
            print('Mirror Request - FAILED - Master already backing up to slave.')
            botmsg = await ctx.send('This server is already being backed up to {}.'.format(self.bot.get_guild(slave_id)))
            await asyncio.sleep(10)
            await botmsg.delete()
            return
        if any([ slave_id in i.keys() for i in self._master_guilds.values() ]):
            print('Mirror Request - FAILED - Slave is in use.')
            botmsg = await ctx.send('That server is already in use.')
            await asyncio.sleep(10)
            await botmsg.delete()
            return
        if slave_id not in self._enslavable_guilds:
            print('Mirror Request - FAILED - Unknown slave.')
            botmsg = await ctx.send('Invalid server ID or server is not enslavable.')
            await asyncio.sleep(10)
            await botmsg.delete()
            return

        print('Mirror Request - SUCCESS')
        self._enslavable_guilds.remove(slave_id)

        if ctx.guild.id in self._master_guilds:
            self._master_guilds[ctx.guild.id][slave_id] = {}
        else:
            self._master_guilds[ctx.guild.id] = {slave_id: {}}

        self._master_guilds[ctx.guild.id][slave_id]['channels'] = {}

        print('Mirror - Fetching all channels and roles.')
        master_guild = ctx.guild
        master_channels = master_guild.channels
        master_roles = master_guild.roles
        master_roles.remove(master_guild.me.top_role)

        slave_guild = self.bot.get_guild(slave_id)
        slave_channels = slave_guild.channels
        slave_roles = [ i for i in slave_guild.roles if not i.is_default() ]
        slave_roles.remove(slave_guild.me.top_role)

        botmsg = await ctx.send('Cleaning slave...')

        print('Mirror - Cleaning {} channels and {} roles from slave.'.format(len(slave_channels),len(slave_roles)))
        for i in slave_roles + slave_channels:
            await i.delete()

        await botmsg.edit(content='Backing up roles...')
        print('Mirror - Backing up {} roles to {}.'.format(len(master_roles),slave_guild))

        self._master_guilds[master_guild.id][slave_guild.id]['roles'] = {master_guild.default_role.id: slave_guild.default_role.id}

        await slave_guild.default_role.edit(permissions=master_guild.default_role.permissions) # set the @everyone perms on slave

        for i in master_guild.roles:
            if i.is_default(): continue
            new_role = await slave_guild.create_role(
                name=i.name,
                permissions=i.permissions,
                colour=i.colour,
                hoist=i.hoist,
                mentionable=i.mentionable)
            self._master_guilds[master_guild.id][slave_guild.id]['roles'][i.id] = new_role.id
        
        await botmsg.edit(content='Backing up channels...')
        print('Mirror - Backing up {} channels to {}.'.format(len(master_channels),slave_guild))

        self._master_guilds[master_guild.id][slave_guild.id]['channels'] = {}
        channels_to_mirror = {}

        for i in master_channels:
            if i.type in channels_to_mirror:
                channels_to_mirror[i.type][i.position] = i
            else:
                channels_to_mirror[i.type] = {i.position:i}


        for i in range(len(channels_to_mirror[discord.ChannelType.category])):
            cc = channels_to_mirror[discord.ChannelType.category][i]
            overwrites = {}
            for k,v in cc.overwrites.items():
                overwrites[slave_guild.get_role(self._master_guilds[master_guild.id][slave_guild.id]['roles'][k.id])] = v

            new_channel = await slave_guild.create_category_channel(
                name=cc.name,
                overwrites=overwrites)
            self._master_guilds[master_guild.id][slave_guild.id]['channels'][cc.id] = new_channel.id
        

        for i in range(len(channels_to_mirror[discord.ChannelType.text])):
            cc = channels_to_mirror[discord.ChannelType.text][i]
            overwrites = {}
            for k,v in cc.overwrites.items():
                overwrites[slave_guild.get_role(self._master_guilds[master_guild.id][slave_guild.id]['roles'][k.id])] = v

            category = None
            if cc.category_id in self._master_guilds[master_guild.id][slave_guild.id]['channels']:
                category = slave_guild.get_channel(self._master_guilds[master_guild.id][slave_guild.id]['channels'][cc.category_id])

            new_channel = await slave_guild.create_text_channel(
                name=cc.name,
                overwrites=overwrites,
                category=category,
                position=cc.position,
                topic=cc.topic,
                slowmode_delay=cc.slowmode_delay,
                nsfw=cc.nsfw
                )
            self._master_guilds[master_guild.id][slave_guild.id]['channels'][cc.id] = new_channel.id

        for i in range(len(channels_to_mirror[discord.ChannelType.voice])):
            cc = channels_to_mirror[discord.ChannelType.voice][i]
            overwrites = {}
            for k,v in cc.overwrites.items():
                overwrites[slave_guild.get_role(self._master_guilds[master_guild.id][slave_guild.id]['roles'][k.id])] = v

            category = None
            if cc.category_id in self._master_guilds[master_guild.id][slave_guild.id]['channels']:
                category = slave_guild.get_channel(self._master_guilds[master_guild.id][slave_guild.id]['channels'][cc.category_id])

            new_channel = await slave_guild.create_voice_channel(
                name=cc.name,
                overwrites=overwrites,
                category=category,
                position=cc.position,
                bitrate=cc.bitrate,
                user_limit=cc.user_limit
                )
            self._master_guilds[master_guild.id][slave_guild.id]['channels'][cc.id] = new_channel.id

        print('Mirror - Banning users.')
        await botmsg.edit(content='Banning banned users.')

        bans = await.master_guild.bans()
        for i in bans:
            await slave_guild.ban(i[0],reason=i[1])

        await botmsg.edit(content='Slave is up to date with master.')
        print('Mirror - Updating slave settings.')

        system_channel = None
        if master_guild.system_channel is not None:
            system_channel = slave_guild.get_channel(self._master_guilds[master_guild.id][slave_guild.id]['channels'][master_guild.system_channel.id])
        icon = await master_guild.icon_url_as(format='png',static_format='png').read()
        await slave_guild.edit(
            name=master_guild.name,
            icon=icon,
            region=master_guild.region,
            afk_channel=master_guild.afk_channel,
            afk_timeout=master_guild.afk_timeout,
            verification_level=master_guild.verification_level,
            default_notifications=master_guild.default_notifications,
            explicit_content_filter=master_guild.explicit_content_filter,
            system_channel=system_channel,
            system_channel_flags=master_guild.system_channel_flags
            )

        await self.save()
        await botmsg.edit(content='Slave is up to date with master.')
        print('Mirror - Initial mirror complete.')

    @commands.command()
    async def enslave(self,ctx):
        if ctx.guild.id in self._enslavable_guilds:
            botmsg = await ctx.send('This server is already marked as enslavable.')
            await asyncio.sleep(10)
            await botmsg.delete()
            return

        botmsg = await ctx.send('Are you sure you want to mark this server, {}, as enslavable?'.format(ctx.guild))
        await botmsg.add_reaction(emotes['x'])
        await botmsg.add_reaction(emotes['check'])
        try:
            answer = None
            while answer == None:
                answer = await self.bot.wait_for('reaction_add',timeout=15)
                if answer[1] == ctx.author and answer[0].emoji == emotes['x']:
                    await botmsg.edit(content='Enslavement canceled.')
                    await botmsg.remove_reaction(emotes['x'],self.bot.user)
                    await botmsg.remove_reaction(emotes['check'],self.bot.user)
                    await asyncio.sleep(10)
                    await botmsg.delete()
                    return
                elif answer[1] == ctx.author and answer[0].emoji == emotes['check']:
                    self._enslavable_guilds.append(ctx.guild.id)
                    await botmsg.edit(content='Server has been marked as enslavable.')
                    await botmsg.remove_reaction(emotes['x'],self.bot.user)
                    await botmsg.remove_reaction(emotes['check'],self.bot.user)
                    return
                answer = None
        except asyncio.TimeoutError:
            await botmsg.edit(content='Enslavement canceled.')
            await botmsg.remove_reaction(emotes['x'],self.bot.user)
            await botmsg.remove_reaction(emotes['check'],self.bot.user)
            await asyncio.sleep(10)
            await botmsg.delete()

def setup(bot):
    bot.add_cog(ServerMirror(bot))
