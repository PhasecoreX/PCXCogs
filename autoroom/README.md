# AutoRoom

This cog facilitates automatic voice channel creation. When a member joins an AutoRoom Source (voice channel), this cog will move them to a brand new AutoRoom that they have control over. Once everyone leaves the AutoRoom, it is automatically deleted.

## For Server Admins - `[p]autoroomset`

Start by having a voice channel, and a category (the voice channel does not need to be in the category, but it can be if you want). The voice channel will be the "AutoRoom Source", where your members will join and then be moved into their own AutoRoom (voice channel). These AutoRooms will be created in the category that you choose.

```
[p]autoroomset create <source_voice_channel> <dest_category>
```

This command will guide you through setting up an AutoRoom Source by asking some questions. If you get a warning about missing permissions, take a look at `[p]autoroomset permissions`, grant the missing permissions, and then run the command again. Otherwise, answer the questions and you'll have a new AutoRoom Source. Give it a try by joining it: if all goes well, you will be moved to a new AutoRoom, where you can do all of the `[p]autoroom` commands.

There are some additional configuration options for AutoRoom Sources that you can set by using `[p]autoroomset modify`. You can also check out `[p]autoroomset access`, which controls whether admins (default yes) or moderators (default no) can see and join private AutoRooms. For an overview of all of your settings, use `[p]autoroomset settings`.

## For Members - `[p]autoroom`

Once you join an AutoRoom Source, you will be moved into a brand new AutoRoom (voice channel). This is your AutoRoom, you can do whatever you want with it. Use the `[p]autoroom` command to check out all the different things you can do. Some examples include:

- Check its current settings with `[p]autoroom settings`
- Make it a public AutoRoom with `[p]autoroom public`
- Make it a private AutoRoom with `[p]autoroom private`
- Kick/ban users (or entire roles) from your AutoRoom with `[p]autoroom deny` (useful for public AutoRooms)
- Allow users (or roles) into your AutoRoom with `[p]autoroom allow` (useful for private AutoRooms)
- If your AutoRoom has an associated text channel, you can manage the messages in your text channel

When everyone leaves your AutoRoom, it (and the associated text channel, if it exists) will automatically be deleted.