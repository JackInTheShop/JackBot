from datetime import datetime as date
from discord.ext import commands
from io import BytesIO
import discord
import json
import re

class ServerBackup(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.sent_by_bot = 0

    @commands.command()
    async def backup(self,ctx,dump=None):
        backup = {}
        backup['name'] = ctx.guild.name
        backup['emojis'] = []
        for emoji in ctx.guild.emojis:
            backup['emojis'].append({
                'name': emoji.name,
                'url': str(emoji.url)})
        backup['region'] = ctx.guild.region.value
        backup['afk_timeout'] = ctx.guild.afk_timeout
        backup['icon_url'] = str(ctx.guild.icon_url_as(format='png',static_format='png'))
        backup['banner_url'] = str(ctx.guild.banner_url_as(format='png'))
        backup['splash_url'] = str(ctx.guild.splash_url_as(format='png'))
        backup['description'] = ctx.guild.description
        backup['mfa_level'] = ctx.guild.mfa_level
        backup['verification_level'] = ctx.guild.verification_level.value
        backup['default_notifications'] = ctx.guild.default_notifications.value
        backup['system_channel_flags'] = ctx.guild.system_channel_flags.value
        backup['explicit_content_filter'] = ctx.guild.explicit_content_filter.value

        bans = await ctx.guild.bans()
        backup['bans'] = { ban.user.id: ban.reason for ban in bans }

        backup['roles'] = []
        for role in ctx.guild.roles:
            role_backup = {
                'name': role.name,
                'hoist': role.hoist,
                'mentionable': role.mentionable,
                'permissions': role.permissions.value,
                'colour': role.colour.value
                }
            # if not role.is_default(): role_backup['members'] = [user.id for user in role.members]
            backup['roles'].append(role_backup)

        backup['categories'] = []
        categories = []
        for category in ctx.guild.categories:
            categories.append(category.id)
            backup['categories'].append({
                'name': category.name,
                'overwrites': self.backup_overwrites(category.overwrites)
            })

        backup['text_channels'] = []
        text_channels = []
        for channel in ctx.guild.text_channels:
            text_channels.append(channel.id)
            backup['text_channels'].append({
                'name': channel.name,
                'category': categories.index(channel.category_id) if channel.category_id else None,
                'topic': channel.topic,
                'slowmode_delay': channel.slowmode_delay,
                'overwrites': self.backup_overwrites(channel.overwrites),
                'nsfw': channel.nsfw,
                'pins': self.backup_pins(await channel.pins())
            })

        backup['voice_channels'] = []
        voice_channels = []
        for channel in ctx.guild.voice_channels:
            voice_channels.append(channel.id)
            backup['voice_channels'].append({
                'name': channel.name,
                'category': categories.index(channel.category_id) if channel.category_id else None,
                'bitrate': channel.bitrate,
                'user_limit': channel.user_limit,
                'overwrites': self.backup_overwrites(channel.overwrites)
            })

        backup['afk_channel'] = None
        if ctx.guild.afk_channel:
            backup['afk_channel'] = voice_channels.index(ctx.guild.afk_channel.id)

        backup['system_channel'] = None
        if ctx.guild.system_channel:
            backup['system_channel'] = text_channels.index(ctx.guild.system_channel.id)

        r = await self.bot.httpx.post('https://mystb.in/documents',data=json.dumps(backup))

        if r.is_error:
            await ctx.send('Backup was successful, but failed to upload to mystb.in')
        else:
            key = json.loads(r.text)['key']
            await ctx.send(f'Backup was successful! Your backup ID is **`{key}`** and can be directly found at <https://mystb.in/{key}>.')

    def backup_pins(self,pins):
        pins_backup = []
        for msg in pins:
            pin = {
                'author': msg.author.id,
                'content': msg.content,
                'attachments': [],
                'embeds': []
            }

            for i in msg.attachments:
                pin['attachments'].append({
                    'filename': i.filename,
                    'url': i.url,
                    'spoiler': i.is_spoiler()
                    })

            for i in msg.embeds:
                pin['embeds'].append(i.to_dict())
            pins_backup.append(pin)

        return pins_backup[::-1]

    def backup_overwrites(self,overwrites):
        overwrites_backup = []
        for role,perm in overwrites.items():
            overwrite = {}
            overwrite['type'] = 'role'
            if type(role) == discord.Role:
                overwrite['value'] = role.position
            else:
                overwrite['type'] = 'member'
                overwrite['value'] = role.id

            permissions = perm.pair()
            overwrite['permissions'] = (permissions[0].value, permissions[1].value)

            overwrites_backup.append(overwrite)
        return overwrites_backup

    async def generate_overwrites(self,overwrites,roles):
        new_overwrites = {}
        for overwrite in overwrites:
            perms = discord.PermissionOverwrite.from_pair(
                discord.Permissions(overwrite['permissions'][0]),
                discord.Permissions(overwrite['permissions'][1]))
            if overwrite['type'] == 'role':
                key = roles[overwrite['value']]
            else:
                key = await self.bot.fetch_user(overwrite['value'])
            new_overwrites[key] = perms

        return new_overwrites


    @commands.Cog.listener()
    async def on_message(self,msg):
        if self.sent_by_bot and msg.type == discord.MessageType.pins_add:
            await msg.delete()
            self.sent_by_bot -= 1
    @commands.command()
    async def restore(self,ctx,haste_id):
        check = re.match(r'^(?:https?://)?(?:mystb\.in)?(?:/raw)?(?:/)?(.*?)(?:/)?$',haste_id).group(1)

        if len(check) < 1:
            botmsg = await ctx.send('Could not parse backup ID.')
            return
        botmsg = await ctx.send(f'Restoring from backup: {check}')

        r = await self.bot.httpx.get(f'https://mystb.in/raw/{check}')

        if r.is_error:
            await botmsg.edit(content='Could not retrieve backup.')
            return

        try:
            backup = r.json()
        except:
            await botmsg.edit(content='The backup is not proper JSON.')

        await ctx.channel.edit(name='backup-contents')

        to_delete = ctx.guild.channels + ctx.guild.roles + list(ctx.guild.emojis)
        to_delete.remove(ctx.channel)
        to_delete.remove(ctx.guild.me.top_role)
        to_delete.remove(ctx.guild.default_role)

        await botmsg.edit(content='Clearing server.')
        for i in to_delete:
            await i.delete()

        await botmsg.edit(content='Updating @everyone.')
        await ctx.guild.default_role.edit(permissions=discord.Permissions(backup['roles'][0]['permissions']))

        await botmsg.edit(content=f'Creating {len(backup["roles"])} roles.')
        roles = []
        for role in backup['roles'][1:][::-1]:
            new_role = await ctx.guild.create_role(
                name=role['name'],
                permissions=discord.Permissions(role['permissions']),
                colour=discord.Colour(role['colour']),
                hoist=role['hoist'],
                mentionable=role['mentionable']
                )
            roles.append(new_role)
        roles = [ctx.guild.default_role] + roles[::-1]

        await botmsg.edit(content=f'Creating {len(backup["categories"])} categories.')
        categories = []
        for category in backup['categories']:
            new_category = await ctx.guild.create_category_channel(
                name=category['name'],
                overwrites=await self.generate_overwrites(category['overwrites'],roles)
                )
            categories.append(new_category)

        await botmsg.edit(content=f'Creating {len(backup["text_channels"])} text channels.')
        text_channels = []
        for channel in backup['text_channels']:
            new_channel = await ctx.guild.create_text_channel(
                name=channel['name'],
                overwrites=await self.generate_overwrites(channel['overwrites'],roles),
                category=categories[channel['category']] if channel['category'] is not None else None,
                topic=channel['topic'],
                slowmode_delay=channel['slowmode_delay'],
                nsfw=channel['nsfw']
                )
            text_channels.append(new_channel)

            if channel['pins']: tmp_webhook = await new_channel.create_webhook(name='Pin Recovery Webhook')
            for i in channel['pins']:
                embeds = []
                files = []
                for j in i['attachments']:
                    r = await self.bot.httpx.get(j['url'])
                    fp = await r.read()
                    files.append(
                        discord.File(
                            fp=BytesIO(fp),
                            filename=j['filename'],
                            spoiler=j['spoiler']))

                for j in i['embeds']: embeds.append(discord.Embed.from_dict(j))
                if len(i['embeds']) < 1: embeds = None
                if len(i['attachments']) < 1: files = None

                user = await self.bot.fetch_user(i['author'])
                pin_msg = await tmp_webhook.send(content=i['content'],files=files,embeds=embeds,username=user.name,avatar_url=user.avatar_url_as(format='png',static_format='png'),wait=True)
                self.sent_by_bot += 1
                await pin_msg.pin()

            if channel['pins']: await tmp_webhook.delete()

        await botmsg.edit(content=f'Creating {len(backup["voice_channels"])} voice channels.')
        voice_channels = []
        for channel in backup['voice_channels']:
            new_channel = await ctx.guild.create_voice_channel(
                name=channel['name'],
                overwrites=await self.generate_overwrites(channel['overwrites'],roles),
                category=categories[channel['category']] if channel['category'] is not None else None,
                bitrate=channel['bitrate'],
                user_limit=channel['user_limit']
                )
            voice_channels.append(new_channel)

        if backup['afk_channel']:
            backup['afk_channel'] = voice_channels[backup['afk_channel']]
        if backup['system_channel']:
            backup['system_channel'] = text_channels[backup['system_channel']]

        await botmsg.edit(content=f'Creating {len(backup["emojis"])} emojis.')
        emojis = []
        for emoji in backup['emojis']:
            emote = await self.bot.httpx.get(emoji['url'])
            if not 'image' in emote.headers['content-type'] or int(emote.headers['content-length']) > 256000: continue
            new_emoji = await ctx.guild.create_custom_emoji(
                name=emoji['name'],
                image=emote.content
                )

            emojis.append(new_emoji)
            if len(emojis) < 50: continue
            break

        for user,reason in backup['bans'].items():
            await ctx.guild.ban(
                user=await self.bot.fetch_user(user),
                reason=reason)


        icon = None
        if backup['icon_url']:
            r = await self.bot.httpx.get(backup['icon_url'])
            if 'image' in r.headers['content-type']:
                icon = r.content

        await botmsg.edit(content='Updating server.')
        system_channel_flags = discord.SystemChannelFlags()
        system_channel_flags.value = backup['system_channel_flags']
        await ctx.guild.edit(
            name=backup['name'],
            description=backup['description'],
            icon=icon,
            region=discord.VoiceRegion(backup['region']),
            afk_channel=backup['afk_channel'],
            afk_timeout=backup['afk_timeout'],
            verification_level=discord.VerificationLevel(backup['verification_level']),
            default_notifications=discord.NotificationLevel(backup['default_notifications']),
            explicit_content_filter=discord.ContentFilter(backup['explicit_content_filter']),
            system_channel=backup['system_channel'],
            system_channel_flags=system_channel_flags
            )

        await botmsg.edit(content='Server restored successfully.')
        if backup['icon_url']:
            await ctx.send(f'Icon: {backup["icon_url"]}')
        if backup['splash_url']:
            await ctx.send(f'Splash: {backup["splash_url"]}')
        if backup['banner_url']:
            await ctx.send(f'Banner: {backup["banner_url"]}')
        if len(emojis) > 0:
            await ctx.send('Emojis Added: ' + ' '.join([str(i) for i in emojis]))
        if len(backup['emojis']) > 0:
            await ctx.send('All Emotes:\n')
            for i in [backup['emojis'][i:i + 20] for i in range(0, len(backup['emojis']), 20)]:
                await ctx.send('\n'.join([f'{j["name"]} — <{j["url"]}>' for j in i]))


def setup(bot):
    bot.add_cog(ServerBackup(bot))

# https://discordapp.com/oauth2/authorize?client_id=632806608916709376&scope=bot
