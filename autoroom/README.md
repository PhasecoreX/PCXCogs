# AutoRoom

This cog facilitates automatic voice channel creation. When a member joins an AutoRoom Source (voice channel), this cog will move them to a brand new AutoRoom that they have control over. Once everyone leaves the AutoRoom, it is automatically deleted.

## For Server Admins - `[p]autoroomset`

Start by having a voice channel, and a category (the voice channel does not need to be in the category, but it can be if you want). The voice channel will be the "AutoRoom Source", where your members will join and then be moved into their own AutoRoom (voice channel). These AutoRooms will be created in the category that you choose.

```
[p]autoroomset create <source_voice_channel> <dest_category>
```

This command will guide you through setting up an AutoRoom Source by asking some questions. If you get a warning about missing permissions, take a look at `[p]autoroomset permissions`, grant the missing permissions, and then run the command again. Otherwise, answer the questions, and you'll have a new AutoRoom Source. Give it a try by joining it: if all goes well, you will be moved to a new AutoRoom, where you can do all of the `[p]autoroom` commands.

There are some additional configuration options for AutoRoom Sources that you can set by using `[p]autoroomset modify`. You can also check out `[p]autoroomset access`, which controls whether admins (default yes) or moderators (default no) can see and join private AutoRooms. For an overview of all of your settings, use `[p]autoroomset settings`.

#### Templates

The default AutoRoom name format is based on the AutoRoom Owners username. Using `[p]autoroomset modify name`, you can choose a default format, or you can set a custom format. For custom formats, you have a couple of variables you can use in your template:

- `{{username}}` - The AutoRoom Owners username
- `{{game}}` - The AutoRoom Owners game they were playing when the AutoRoom was created, or blank if they were not plating a game.
- `{{dupenum}}` - A number, starting at 1, that will increment when the generated AutoRoom name would be a duplicate of an already existing AutoRoom.

You are also able to use `if`/`elif`/`else`/`endif` statements in order to conditionally show or hide parts of your template. Here are the templates for the two default formats included:

- `username` - `{{username}}'s Room{% if dupenum > 1 %} ({{dupenum}}){% endif %}`
- `game` - `{{game}}{% if not game %}{{username}}'s Room{% endif %}{% if dupenum > 1 %} ({{dupenum}}){% endif %}`

The username format is pretty self-explanatory: put the username, along with "'s Room" after it. For the game format, we put the game name, and then if there isn't a game, show `{{username}}'s Room` instead. Remember, if no game is being played, `{{game}}` won't return anything.

The last bit of both of these is `{% if dupenum > 1 %} ({{dupenum}}){% endif %}`. With this, we are checking if `dupenum` is greater than 1. If it is, we display ` ({{dupenum}})` at the end of our room name. This way, only duplicate named rooms will ever get a ` (2)`, ` (3)`, etc. appended to them, no ` (1)` will be shown.

This template format can also be used for the message hint sent to new AutoRoom text channels.

## For Members - `[p]autoroom`

Once you join an AutoRoom Source, you will be moved into a brand new AutoRoom (voice channel). This is your AutoRoom, you can do whatever you want with it. Use the `[p]autoroom` command to check out all the different things you can do. Some examples include:

- Check its current settings with `[p]autoroom settings`
- Make it a public AutoRoom with `[p]autoroom public`
- Make it a private AutoRoom with `[p]autoroom private`
- Kick/ban users (or entire roles) from your AutoRoom with `[p]autoroom deny` (useful for public AutoRooms)
- Allow users (or roles) into your AutoRoom with `[p]autoroom allow` (useful for private AutoRooms)
- If your AutoRoom has an associated text channel, you can manage the messages in your text channel

When everyone leaves your AutoRoom, it (and the associated text channel, if it exists) will automatically be deleted.