"""Perfis de conteúdo: cada um ajusta pesos, palavras-gatilho, cores, hashtags e o contexto da IA."""

PERFIS = {
    "gta6": {
        "nome": "GTA 6",
        "padrao": {
            "n_clipes": 6, "dur_min": 20, "dur_max": 50,
            "cor": "#FF2E88", "preset": "vice",
            "peso_volume": 0.5, "peso_voz": 1.5, "peso_chat": 2.0, "peso_fala": 1.25,
            "hashtags": "#GTA6 #GTAVI #GTA #RockstarGames #ViceCity",
        },
        "gatilhos": [
            "wasted", "morri", "morreu", "procurado", "estrela", "estrelas", "polícia", "policia",
            "fuga", "perseguição", "perseguicao", "missão", "missao", "mission passed", "passei",
            "bug", "glitch", "lucia", "jason", "vice city", "leonida", "assalto", "roubo",
            "explodiu", "explosão", "explosao", "helicóptero", "helicoptero", "tiro", "cinco estrelas",
            "5 estrelas", "easter egg", "segredo", "rockstar", "gráfico", "grafico", "física", "fisica",
            "jacaré", "jacare", "flamingo", "praia", "carro", "moto", "lancha", "atropel", "capotou",
        ],
        # palavra na fala -> hashtag extra
        "hashtags_extra": {
            "lucia": "#Lucia", "jason": "#Jason", "leonida": "#Leonida", "vice city": "#ViceCity",
            "bug": "#GTA6Bug", "glitch": "#GTA6Glitch", "polícia": "#GTA6Policia", "policia": "#GTA6Policia",
            "assalto": "#GTA6Assalto", "roubo": "#GTA6Assalto", "easter egg": "#EasterEgg",
            "carro": "#GTA6Carros", "missão": "#GTA6Missao", "missao": "#GTA6Missao",
            "wasted": "#Wasted", "jacaré": "#GTA6Jacare", "jacare": "#GTA6Jacare",
        },
        "hashtags_gerais": ["#gaming", "#gamer", "#gameplay", "#cortes", "#fyp", "#viral"],
        "contexto_ia": (
            "cortes de lives de GTA 6 (Grand Theft Auto VI, da Rockstar Games, lançado em 19/11/2026 "
            "para PS5 e Xbox Series X|S; se passa no estado de Leonida, com Vice City; protagonistas "
            "Lucia e Jason). Público brasileiro gamer. Destaque perseguições, bugs, reações, momentos "
            "engraçados, descobertas e segredos do mapa."
        ),
        "cta": "Segue pra mais cortes de GTA 6! 🌴",
    },
    "geral": {
        "nome": "Geral",
        "padrao": {"hashtags": "#cortes #live"},
        "gatilhos": [],
        "hashtags_extra": {},
        "hashtags_gerais": ["#fyp", "#viral", "#foryou"],
        "contexto_ia": "cortes de lives em geral, público brasileiro.",
        "cta": "Segue pra mais cortes!",
    },
}


def obter(nome):
    return PERFIS.get(nome or "gta6", PERFIS["geral"])
