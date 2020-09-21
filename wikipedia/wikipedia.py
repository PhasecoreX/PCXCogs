"""Wikipedia cog for Red-DiscordBot ported by PhasecoreX."""
import aiohttp
import discord
from redbot.core import __version__ as redbot_version
from redbot.core import commands
from redbot.core.utils.chat_formatting import error, warning

__author__ = "PhasecoreX"


class Wikipedia(commands.Cog):
    """Look up stuff on Wikipedia."""

    base_url = "https://en.wikipedia.org/w/api.php"
    headers = {"user-agent": "Red-DiscordBot/" + redbot_version}
    footer_icon = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Wikimedia-logo.png"
        "/600px-Wikimedia-logo.png"
    )

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.command(aliases=["wiki"])
    async def wikipedia(self, ctx: commands.Context, *, query: str):
        """Get information from Wikipedia."""
        payload = self.generate_payload(query)
        conn = aiohttp.TCPConnector()
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(
                self.base_url, params=payload, headers=self.headers
            ) as res:
                result = await res.json()

        try:
            # Get the last page. Usually this is the only page.
            for page in result["query"]["pages"]:
                title = page["title"]
                description = page["extract"].strip().replace("\n", "\n\n")
                image = (
                    page["original"]["source"]
                    if "original" in page and "source" in page["original"]
                    else None
                )
                url = page["fullurl"]

            if len(description) > 1500:
                description = description[:1500].strip()
                description += "... [(read more)]({})".format(url)

            embed = discord.Embed(
                title="Wikipedia: {}".format(title),
                description=u"\u2063\n{}\n\u2063".format(description),
                color=discord.Color.blue(),
                url=url,
            )
            if image:
                embed.set_image(url=image)
            embed.set_footer(
                text="Information provided by Wikimedia", icon_url=self.footer_icon
            )
            await ctx.send(embed=embed)

        except KeyError:
            await ctx.send(
                error("I'm sorry, I couldn't find \"{}\" on Wikipedia".format(query))
            )
        except discord.Forbidden:
            await ctx.send(
                warning("I'm not allowed to do embeds here...\n{}".format(url))
            )

    @staticmethod
    def generate_payload(query: str):
        """Generate the payload for Wikipedia based on a query string."""
        payload = {}
        # Main module
        payload["action"] = "query"  # Fetch data from and about MediaWiki
        payload["format"] = "json"  # Output data in JSON format

        # format:json options
        payload["formatversion"] = "2"  # Modern format

        # action:query options
        payload["titles"] = query.replace(" ", "_")  # A list of titles to work on
        payload["redirects"] = "1"  # Automatically resolve redirects
        payload["prop"] = "extracts|info|pageimages"  # Which properties to get

        # action:query/prop:extracts options
        payload["exintro"] = "1"  # Return only content before the first section
        payload["explaintext"] = "1"  # Return extracts as plain text

        # action:query/prop:info options
        payload["inprop"] = "url"  # Gives a full URL for each page

        # action:query/prop:pageimages options
        payload["piprop"] = "original"  # Return URL of page image, if any
        return payload
