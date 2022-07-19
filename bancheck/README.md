# BanCheck

This cog allows server admins to check their members against multiple external ban lists. It can also automatically check new members that join the server, and optionally ban them if they appear in a list. This cog is decently complex to set up, so hopefully this document can help you out.

## For Bot Owners - `[p]banchecksetglobal`

There are certain ban list APIs that can only be set up for the entire bot (instead of per server). Usually this is due to the fact that your bot needs to go through a verification process before you get an API key, and only one key per bot is issued. At the time of writing, [Ravy](https://ravy.org/api) is the only one that does this. Once you set the API key, the ban list checking functionality for that service will be available for use in all servers your bot is a part of. The admins of the servers will need to manually enable the service for checking, however.

```
[p]banchecksetglobal settings
```

Using this command will list all the bot-wide ban list services that are supported. Clicking the link will bring you to that services website, where you can apply for an API key. Once you have an API key, you can check `[p]banchecksetglobal api <service_name>` for info on how to set the API. Once you have set the API correctly, you can again check `[p]banchecksetglobal settings` and see that your service is set.

That's all the setup you need to do for these services. To actually use these services, see below.

## For Server Admins - `[p]bancheckset`

Your best friend for setting up BanCheck is the following command:

```
[p]bancheckset settings
```

Using that will give you a rundown of the current state of the BanCheck cog in your server (and I am quite proud of it myself!)

## Services

Since you don't have any enabled services, the above command will instruct you to check out `[p]bancheckset service settings` for more information. This will give you an overview of which services you can enable or disable, and which ones need an API key (either from you or the bot owner).

If a service is missing an API key, you can follow the link to the services website and obtain an API key. These API keys can be set with `[p]bancheckset service api <service> [api_key]`. If a service is missing a global API key, the API key can only be set up by the bot owner (bot owners, see above section).

You can enable or disable services at any time (even if their API key is missing) by using `[p]bancheckset service <enable|disable> <service_name>`. If enabled and their API key is missing, the service will begin working automatically once you (or the bot owner) supplies it. This can be useful, for example, by enabling a service that requires a global API key, and then once the bot owner gets around to verifying their bot and setting the global API key, it will automatically be used for ban checking in your server.

At this point, you have some services enabled, and can verify this in `[p]bancheckset settings`. You are now able to use the `[p]bancheck` command to manually check other members (or yourself), either with their ID or their mention.

## AutoCheck

If you want every joining member to automatically be checked with the enabled services, head on over to `[p]bancheckset autocheck`. From there, you can set the channel that the AutoCheck notifications will be sent to. Verify that you have set this up correctly with `[p]bancheckset settings`.

## AutoBan

In addition to automatically checking each new member, you can set it so that anyone appearing on a services ban list will be banned on the spot, with the user getting a message explaining why they were banned (they were on a specific global ban list). Check out `[p]bancheckset autoban` to enable or disable AutoBan functionality for specific services. Again, verify that you have set this up correctly with `[p]bancheckset settings`.

## Finish!

Once you have done the above, you can once again verify that you have set everything up correctly with `[p]bancheckset settings`. Enjoy!
