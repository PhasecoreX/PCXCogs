from .decodebinary import DecodeBinary


def setup(bot):
    bot.add_cog(DecodeBinary(bot))
