"""Wikipedia cog for Red-DiscordBot ported by PhasecoreX."""
import aiohttp
import discord
from dateutil.parser import isoparse
from redbot.core import __version__ as redbot_version
from redbot.core import commands
from redbot.core.utils.chat_formatting import error, warning
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

__author__ = "PhasecoreX"


class Wikipedia(commands.Cog):
    """Look up stuff on Wikipedia."""

    DISAMBIGUATION_CAT = "Category:All disambiguation pages"

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.command(aliases=["wiki"])
    async def wikipedia(self, ctx: commands.Context, *, query: str):
        """Get information from Wikipedia."""
        async with ctx.typing():
            payload = self.generate_payload(query)
            conn = aiohttp.TCPConnector()
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.get(
                    "https://en.wikipedia.org/w/api.php",
                    params=payload,
                    headers={"user-agent": "Red-DiscordBot/" + redbot_version},
                ) as res:
                    result = await res.json()

            embeds = []
            if "query" in result and "pages" in result["query"]:
                result["query"]["pages"].sort(
                    key=lambda unsorted_page: unsorted_page["index"]
                )
                for page in result["query"]["pages"]:
                    try:
                        if (
                            "categories" in page
                            and page["categories"]
                            and "title" in page["categories"][0]
                            and page["categories"][0]["title"]
                            == self.DISAMBIGUATION_CAT
                        ):
                            continue  # Skip disambiguation pages
                        if not ctx.channel.permissions_for(ctx.me).embed_links:
                            # No embeds here :(
                            await ctx.send(
                                warning(
                                    f"I'm not allowed to do embeds here, so here's the first result:\n{page['fullurl']}"
                                )
                            )
                            return
                        embeds.append(self.generate_embed(page))
                        if not ctx.channel.permissions_for(ctx.me).add_reactions:
                            break  # Menu can't function so only show first result
                    except KeyError:
                        pass

        if not embeds:
            await ctx.send(
                error(f"I'm sorry, I couldn't find \"{query}\" on Wikipedia")
            )
        elif len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await menu(ctx, embeds, DEFAULT_CONTROLS, timeout=60.0)

    def generate_payload(self, query: str):
        """Generate the payload for Wikipedia based on a query string."""
        query_tokens = query.split()
        payload = {
            # Main module
            "action": "query",  # Fetch data from and about MediaWiki
            "format": "json",  # Output data in JSON format
            # format:json options
            "formatversion": "2",  # Modern format
            # action:query options
            "generator": "search",  # Get list of pages by executing a query module
            "redirects": "1",  # Automatically resolve redirects
            "prop": "extracts|info|pageimages|revisions|categories",  # Which properties to get
            # action:query/generator:search options
            "gsrsearch": f"intitle:{' intitle:'.join(query_tokens)}",  # Search for page titles
            # action:query/prop:extracts options
            "exintro": "1",  # Return only content before the first section
            "explaintext": "1",  # Return extracts as plain text
            # action:query/prop:info options
            "inprop": "url",  # Gives a full URL for each page
            # action:query/prop:pageimages options
            "piprop": "original",  # Return URL of page image, if any
            # action:query/prop:revisions options
            "rvprop": "timestamp",  # Return timestamp of last revision
            # action:query/prop:revisions options
            "clcategories": self.DISAMBIGUATION_CAT,  # Only list this category
        }
        return payload

    @staticmethod
    def generate_embed(page_json):
        """Generate the embed for the json page."""
        title = page_json["title"]
        description = page_json["extract"].strip().replace("\n", "\n\n")
        image = (
            page_json["original"]["source"]
            if "original" in page_json and "source" in page_json["original"]
            else None
        )
        url = page_json["fullurl"]
        timestamp = (
            isoparse(page_json["revisions"][0]["timestamp"])
            if "revisions" in page_json
            and page_json["revisions"]
            and "timestamp" in page_json["revisions"][0]
            else None
        )

        if len(description) > 1000:
            description = description[:1000].strip()
            description += f"... [(read more)]({url})"

        embed = discord.Embed(
            title=f"Wikipedia: {title}",
            description=description,
            color=discord.Color.blue(),
            url=url,
            timestamp=timestamp,
        )
        if image:
            embed.set_image(url=image)
        text = "Information provided by Wikimedia"
        if timestamp:
            text += f"\nArticle last updated"
        embed.set_footer(
            text=text,
            icon_url=(
                "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Wikimedia-logo.png"
                "/600px-Wikimedia-logo.png"
            ),
        )
        return embed
