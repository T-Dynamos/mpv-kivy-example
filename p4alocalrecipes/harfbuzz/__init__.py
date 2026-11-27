from pythonforandroid.recipes.harfbuzz import HarfbuzzRecipe as BaseHarfbuzzRecipe


class HarfbuzzRecipe(BaseHarfbuzzRecipe):
    def get_recipe_env(self, arch=None):
        env = super().get_recipe_env(arch)
        flags = " -DHB_NO_PRAGMA_GCC_DIAGNOSTIC_ERROR"
        env["CFLAGS"] = env.get("CFLAGS", "") + flags
        env["CXXFLAGS"] = env.get("CXXFLAGS", "") + flags
        return env


recipe = HarfbuzzRecipe()
