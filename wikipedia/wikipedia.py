"""Wikipedia cog for Red-DiscordBot ported by PhasecoreX."""
import re
from contextlib import suppress
from typing import Any

import aiohttp
import discord
from dateutil.parser import isoparse
from redbot.core import __version__ as redbot_version
from redbot.core import commands
from redbot.core.utils.chat_formatting import error, warning
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

MAX_DESCRIPTION_LENGTH = 1000


class Wikipedia(commands.Cog):
    """Look up stuff on Wikipedia."""

    __author__ = "PhasecoreX"
    __version__ = "3.1.0"

    DISAMBIGUATION_CAT = "Category:All disambiguation pages"
    WHITESPACE = re.compile(r"[\n\s]{4,}")
    NEWLINES = re.compile(r"\n+")

    #
    # Red methods
    #

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Show version in help."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, _requester: str, _user_id: int) -> None:
        """Nothing to delete."""
        return

    #
    # Command methods
    #

    @commands.command(aliases=["wiki"])
    async def wikipedia(self, ctx: commands.Context, *, query: str) -> None:
        """Get information from Wikipedia."""
        can_not_embed_links = False
        can_not_add_reactions = False
        can_not_read_history = False
        if isinstance(ctx.me, discord.Member):
            can_not_embed_links = not ctx.channel.permissions_for(ctx.me).embed_links
            can_not_add_reactions = not ctx.channel.permissions_for(
                ctx.me
            ).add_reactions
            can_not_read_history = not ctx.channel.permissions_for(
                ctx.me
            ).read_message_history
        only_first_result = (
            can_not_embed_links or can_not_add_reactions or can_not_read_history
        )
        async with ctx.typing():
            embeds, url = await self.perform_search(
                query, only_first_result=only_first_result
            )

        if not embeds:
            await ctx.send(
                error(f"I'm sorry, I couldn't find \"{query}\" on Wikipedia")
            )
        elif can_not_embed_links:
            await ctx.send(
                warning(
                    f"I'm not allowed to do embeds here, so here's the first result:\n{url}"
                )
            )
        elif can_not_add_reactions:
            embeds[0].set_author(
                name="Result 1 (I need add reactions permission to show more)"
            )
            await ctx.send(embed=embeds[0])
        elif can_not_read_history:
            embeds[0].set_author(
                name="Result 1 (I need read message history permission to show more)"
            )
            await ctx.send(embed=embeds[0])
        elif len(embeds) == 1:
            embeds[0].set_author(name="Result 1 of 1")
            await ctx.send(embed=embeds[0])
        else:
            count = 0
            for embed in embeds:
                count += 1
                embed.set_author(name=f"Result {count} of {len(embeds)}")
            await menu(ctx, embeds, DEFAULT_CONTROLS, timeout=60.0)

    #
    # Public methods
    #

    def generate_payload(self, query: str) -> dict[str, str]:
        """Generate the payload for Wikipedia based on a query string."""
        query_tokens = query.split()
        return {
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

    async def perform_search(
        self, query: str, *, only_first_result: bool = False
    ) -> tuple[list[discord.Embed], str | None]:
        """Query Wikipedia."""
        payload = self.generate_payload(query)
        async with aiohttp.ClientSession() as session, session.get(
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
                with suppress(KeyError):
                    if (
                        "categories" in page
                        and page["categories"]
                        and "title" in page["categories"][0]
                        and page["categories"][0]["title"] == self.DISAMBIGUATION_CAT
                    ):
                        continue  # Skip disambiguation pages
                    embeds.append(self.generate_embed(page))
                    if only_first_result:
                        return embeds, page["fullurl"]
        return embeds, None

    def generate_embed(self, page_json: dict[str, Any]) -> discord.Embed:
        """Generate the embed for the json page."""
        title = page_json["title"]
        description: str = page_json["extract"].strip()
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

        whitespace_location = None
        whitespace_check_result = self.WHITESPACE.search(description)
        if whitespace_check_result:
            whitespace_location = whitespace_check_result.start()
        if whitespace_location:
            description = description[:whitespace_location].strip()
        description = self.NEWLINES.sub("\n\n", description)
        if len(description) > MAX_DESCRIPTION_LENGTH or whitespace_location:
            description = description[:MAX_DESCRIPTION_LENGTH].strip()
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
            text += "\nArticle last updated"
        embed.set_footer(
            text=text,
            icon_url=(
                "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Wikimedia-logo.png"
                "/600px-Wikimedia-logo.png"
            ),
        )
        return embed
