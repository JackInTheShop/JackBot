from datetime import datetime as date
from discord.ext import commands
from io import BytesIO
import discord
import json
import re

class ServerBackup(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

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
        backup['bans'] = { user.id: reason for user,reason in bans }

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
                'nsfw': channel.nsfw
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
            await ctx.send('Backup was successful, but failed to upload to dpaste.com')
        else:
            key = json.loads(r.text)['key']
            await ctx.send('Backup was successful! Your backup ID is `{key}` and can be directly found at <https://mystb.in/{key}>.'.format(key=key))


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

    def generate_overwrites(self,overwrites,roles):
        new_overwrites = {}
        for overwrite in overwrites:
            perms = discord.PermissionOverwrite.from_pair(
                discord.Permissions(overwrite['permissions'][0]),
                discord.Permissions(overwrite['permissions'][1]))
            if overwrite['type'] == 'role':
                key = roles[overwrite['value']]
            else:
                key = self.bot.get_user(overwrite['value'])
            new_overwrites[key] = perms

        return new_overwrites

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

        to_delete = ctx.guild.channels + ctx.guild.roles
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
            print(category)
            new_category = await ctx.guild.create_category_channel(
                name=category['name'],
                overwrites=self.generate_overwrites(category['overwrites'],roles)
                )
            categories.append(new_category)
        print(categories)
        await botmsg.edit(content=f'Creating {len(backup["text_channels"])} text channels.')
        text_channels = []
        for channel in backup['text_channels']:
            print(channel)
            print(categories[channel['category']] if channel['category'] else None,)
            new_channel = await ctx.guild.create_text_channel(
                name=channel['name'],
                overwrites=self.generate_overwrites(channel['overwrites'],roles),
                category=categories[channel['category']] if channel['category'] is not None else None,
                topic=channel['topic'],
                slowmode_delay=channel['slowmode_delay'],
                nsfw=channel['nsfw']
                )
            text_channels.append(new_channel)

        await botmsg.edit(content=f'Creating {len(backup["voice_channels"])} voice channels.')
        voice_channels = []
        for channel in backup['voice_channels']:
            new_channel = await ctx.guild.create_voice_channel(
                name=channel['name'],
                overwrites=self.generate_overwrites(channel['overwrites'],roles),
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
            if not 'image' in emote.headers['content-type']:
                continue
            new_emoji = await ctx.guild.create_custom_emoji(
                name=emoji['name'],
                image=emote.content
                )

            emojis.append(new_emoji)
            if len(emojis) < 50: continue
            break

        icon = await self.bot.httpx.get(backup['icon_url'])
        if not 'image' in icon.headers['content-type']:
            icon = None
        else:
            icon = icon.content

        await botmsg.edit(content='Updating server.')
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
            system_channel_flags=discord.SystemChannelFlags(backup['system_channel_flags'])
            )

        await botmsg.edit(content='Server restored successfully.')
        if backup['icon_url']:
            await ctx.send(f'Server Icon: {backup["icon_url"]}')
        if backup['splash_url']:
            await ctx.send(f'Server Icon: {backup["splash_url"]}')
        if backup['banner_url']:
            await ctx.send(f'Server Icon: {backup["banner_url"]}')
        if len(emojis) > 0:
            await ctx.send('Emojis Added: ' + ', '.join([str(i) for i in emojis]))
        if len(backup['emojis']) > 0:
            await ctx.send('All Emotes:\n')
            for i in [backup['emojis'][i:i + 20] for i in range(0, len(backup['emojis']), 20)]:
                await ctx.send('\n'.join([f'{j["name"]} — {j["url"]}' for j in i]))
        print('Done.')


def setup(bot):
    bot.add_cog(ServerBackup(bot))
