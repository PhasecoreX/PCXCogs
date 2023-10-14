# PCXCogs

PhasecoreX's Cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot/releases).

[![Red-DiscordBot](https://img.shields.io/badge/red--discordbot-v3-red)](https://github.com/Cog-Creators/Red-DiscordBot/releases)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/PhasecoreX/PCXCogs/master.svg)](https://results.pre-commit.ci/latest/github/PhasecoreX/PCXCogs/master)
[![Chat Support](https://img.shields.io/discord/608057344487849989)](https://discord.gg/QzdPp2b)
[![BuyMeACoffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-orange)](https://buymeacoff.ee/phasecorex)
[![PayPal](https://img.shields.io/badge/paypal-donate-blue)](https://paypal.me/pcx)

To add these wonderful cogs to your instance, run this command first (`[p]` is your bot prefix):

```
[p]repo add pcxcogs https://github.com/PhasecoreX/PCXCogs
```

Then install your cog(s) of choice:

```
[p]cog install pcxcogs <cog_name>
```

Finally, load your cog(s):

```
[p]load <cog_name>
```

If you don't have an instance, consider using my nice [docker image](https://hub.docker.com/r/phasecorex/red-discordbot)!

If you'd like to contact me, test out my cogs, or stay up to date on my cogs, consider joining my [Discord server](https://discord.gg/QzdPp2b)! You can find me on the Red Cog Support server as well.

## The List of Cogs

### AutoRoom

Automatic voice channel management. When a user joins an AutoRoom source channel, they will be moved into their own personal on-demand voice channel (AutoRoom). Once all users have left the AutoRoom, it is automatically deleted.

### BanCheck

Automatically check users against multiple global ban lists on server join. Other features include automatic banning, manually checking users already on the server, and sending ban reports to supported services.

### BanSync

Automatically sync bans between servers that the bot is in. Supports pulls (one way) and two way syncing of bans and unbans.

### DecodeBinary

Automatically decode binary strings in chat. Any message that the bot thinks is binary will be decoded to regular text. Based on a Reddit bot, and was my first cog!

### Dice

Perform complex dice rolling. Supports dice notation (such as 3d6+3), shows all roll results, and can be configured to limit the number of dice a user can roll at once.

### Heartbeat

Monitor the uptime of your bot by sending heartbeat pings to a configurable URL (healthchecks.io for instance).

### NetSpeed

Test the internet speed of the server your bot is hosted on. Runs an internet speedtest and prints the results. Only the owner can run this.

### ReactChannel

Per-channel automatic reaction tools, where every message in a channel will have reactions added to them. Supports turning a channel into a checklist (checkmark will delete the message), an upvote-like system (affects a user's karma total), or a custom channel.

### RemindMe

Set reminders for yourself. Ported from v2; originally by Twentysix26. I've made many enhancements to it as well.

### UpdateNotify

Automatically check for updates to Red-DiscordBot, notifying the owner. Also checks for updates to [my docker image](https://hub.docker.com/r/phasecorex/red-discordbot) if you are using that.

### UwU

Uwuize messages. Takes the pwevious mwessage and uwuizes it. Sowwy.

### Wikipedia

Look up articles on Wikipedia. Ported from v2; originally by PaddoInWonderland. I've made some enhancements to it as well.
