# AutoRoom

This cog facilitates automatic voice channel creation. When a member joins an AutoRoom Source (voice channel), this cog will move them to a brand new AutoRoom that they have control over. Once everyone leaves the AutoRoom, it is automatically deleted.

## For Members - `[p]autoroom`

Once you join an AutoRoom Source, you will be moved into a brand new AutoRoom (voice channel). This is your AutoRoom, you can do whatever you want with it. Use the `[p]autoroom` command to check out all the different things you can do. Some examples include:

-   Check its current settings with `[p]autoroom settings`
-   Make it a public AutoRoom with `[p]autoroom public` (everyone can see and join your AutoRoom)
-   Make it a locked AutoRoom with `[p]autoroom locked` (everyone can see, but nobody can join your AutoRoom)
-   Make it a private AutoRoom with `[p]autoroom private` (nobody can see and join your AutoRoom)
-   Kick/ban users (or entire roles) from your AutoRoom with `[p]autoroom deny` (useful for public AutoRooms)
-   Allow users (or roles) into your AutoRoom with `[p]autoroom allow` (useful for locked and private AutoRooms)
-   You can manage the messages in your AutoRooms associated text channel

When everyone leaves your AutoRoom, it will automatically be deleted.

## For Server Admins - `[p]autoroomset`

Start by having a voice channel, and a category (the voice channel does not need to be in the category, but it can be if you want). The voice channel will be the "AutoRoom Source", where your members will join and then be moved into their own AutoRoom (voice channel). These AutoRooms will be created in the category that you choose.

```
[p]autoroomset create <source_voice_channel> <dest_category>
```

This command will guide you through setting up an AutoRoom Source by asking some questions. If you get a warning about missing permissions, take a look at `[p]autoroomset permissions`, grant the missing permissions, and then run the command again. Otherwise, answer the questions, and you'll have a new AutoRoom Source. Give it a try by joining it: if all goes well, you will be moved to a new AutoRoom, where you can do all of the `[p]autoroom` commands.

There are some additional configuration options for AutoRoom Sources that you can set by using `[p]autoroomset modify`. You can also check out `[p]autoroomset access`, which controls whether admins (default yes) or moderators (default no) can see and join private AutoRooms. For an overview of all of your settings, use `[p]autoroomset settings`.

#### Member Roles and Hidden Sources

The AutoRoom Source will behave in a certain way, depending on what permissions it has. If the `@everyone` role is denied the connect permission (and optionally the view channel permission), the AutoRoom Source and AutoRooms will behave in a member role style. Any roles that are allowed to connect on the AutoRoom Source will be considered the "member roles". Only members of the server with one or more of these roles will be able to utilize these AutoRooms and their Sources.

For hidden AutoRoom Sources, you can deny the view channel permission for the `@everyone` role, but still allow the connect permission. The members won't be able to see the AutoRoom Source, but any AutoRooms it creates they will be able to see (depending on if it isn't a private AutoRoom). Ideally you would have a role that is allowed to see the AutoRoom Source, that role is allowed to create AutoRooms, but then can invite anyone to their AutoRooms.

You can of course do both of these, where the `@everyone` role is denied view channel and connect, and your member role is denied the view channel permission, but is allowed the connect permission. Non-members will never see the AutoRoom Source and AutoRooms, and the members will not see the AutoRoom Source, but will see AutoRooms.

#### Templates

The default AutoRoom name format is based on the AutoRoom Owners username. Using `[p]autoroomset modify name`, you can choose a default format, or you can set a custom format. For custom formats, you have a couple of variables you can use in your template:

-   `{{username}}` - The AutoRoom Owners username
-   `{{game}}` - The AutoRoom Owners game they were playing when the AutoRoom was created, or blank if they were not plating a game.
-   `{{dupenum}}` - A number, starting at 1, that will increment when the generated AutoRoom name would be a duplicate of an already existing AutoRoom.

You are also able to use `if`/`elif`/`else`/`endif` statements in order to conditionally show or hide parts of your template. Here are the templates for the two default formats included:

-   `username` - `{{username}}'s Room{% if dupenum > 1 %} ({{dupenum}}){% endif %}`
-   `game` - `{{game}}{% if not game %}{{username}}'s Room{% endif %}{% if dupenum > 1 %} ({{dupenum}}){% endif %}`

The username format is pretty self-explanatory: put the username, along with "'s Room" after it. For the game format, we put the game name, and then if there isn't a game, show `{{username}}'s Room` instead. Remember, if no game is being played, `{{game}}` won't return anything.

The last bit of both of these is `{% if dupenum > 1 %} ({{dupenum}}){% endif %}`. With this, we are checking if `dupenum` is greater than 1. If it is, we display ` ({{dupenum}})` at the end of our room name. This way, only duplicate named rooms will ever get a ` (2)`, ` (3)`, etc. appended to them, no ` (1)` will be shown.

Finally, you can use filters in order to format your variables. They are specified by adding a pipe, and then the name of the filter. The following are the currently implemented filters:

-   `{{username | lower}}` - Will lowercase the variable, the username in this example
-   `{{game | upper}}` - Will uppercase the variable, the game name in this example

This template format can also be used for the message hint sent to new AutoRooms built in text channels. For that, you can also use this variable:

-   `{{mention}}` - The AutoRoom Owners mention
