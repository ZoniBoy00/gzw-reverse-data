# Gray Zone Warfare — Reverse Engineering Data

**Game:** Gray Zone Warfare (v0.4.6.0, CL-270156)
**Developer:** Madfinger Games
**Engine:** Unreal Engine 5 (custom build with Skalla animation system)
**Backend:** Nakama (Heroic Labs) + Odin VOIP + EOS
**Extracted:** July 21, 2026

---

## Overview

This repository contains data extracted from the Gray Zone Warfare game client (`GZWClientSteam-Win64-Shipping.exe`, 178 MB) through static binary analysis. The PAK files use a custom UE5 IO Store format that is not currently supported by FModel or other extraction tools.

**What we have:** Backend architecture, RPC structure, server modules, game mechanics, naming conventions
**What we need:** PAK extraction for numerical data (weapon stats, armor values, spawn tables)

---

## Data Organization

```
GrayZoneWarfare/
├── README.md                    ← This file
├── data/                        ← Clean organized data (English)
│   ├── nakama_rpcs/             ← Nakama backend RPC errors and codes
│   │   └── nakama_errors.json
│   ├── endpoints/               ← Server modules and operations
│   │   └── server_modules.json
│   ├── game_assets/             ← Game asset categories
│   │   ├── datatables.json      ← 35 DataTable assets
│   │   ├── weapons.json         ← Weapon and attachment references
│   │   ├── armor.json           ← Armor/vest/helmet references
│   │   ├── ammo.json            ← Ammo caliber references
│   │   ├── medical.json         ← Medical item references
│   │   ├── keys.json            ← Key/keycard references
│   │   ├── quests.json          ← Quest/task references
│   │   └── factions.json        ← Faction references
│   └── config/                  ← Game configuration
│       └── game_settings.json
├── code_analysis/               ← Raw extraction data (JSON)
│   ├── strings/                 ← All extracted strings per binary
│   ├── extract_strings.py       ← Extraction tool
│   └── summary.md               ← Technical summary
├── pak_data/                    ← PAK/UTOC analysis
│   ├── exports/                 ← UTOC parsing results
│   ├── find_aes_key.py          ← AES key search (none found - no encryption)
│   └── read_utoc.py            ← UTOC format parser
├── configs/                     ← Config files from game
└── reports/                     ← Analysis reports
    └── SUMMARY.md               ← Full technical report
```

---

## Key Findings

### 1. Backend Architecture (Nakama)

The game uses **Nakama** (open-source game backend by Heroic Labs) for all online functionality:

| Category | Details |
|---|---|
| **Character Creation** | Faction selection, username validation, appearance, wipe system |
| **Squad System** | Create, join, leave squads; full/incompatible/blocked states |
| **Custom Servers** | Create, update, list, password-protect, transfer ownership, promote members |
| **Matchmaking** | Real-time match find/join/reject, region codes |
| **Moderation** | Kick, ban, RPC violation detection |
| **Hit Validation** | Server-authoritative hit detection with DOS protection |
| **Quest System** | Server-managed quest progression |
| **Modding Support** | Officially referenced in code (`Server_ModdingRequestOperation`) |
| **Server Types** | Development, Experimental, Production |

**Source paths reveal 10+ server modules:**
- `MadfingerCoreOnline/` — Core Nakama integration
- `MadfingerCoreServerInfo/` — Server info provider
- `MadfingerGame/` — Game logic (matchmaker, moderation, squad, notifications)

### 2. Factions (134 references)

Factions found in game files beyond what the wiki lists:

| Faction | Description |
|---|---|
| `CambodianArmsTraffickers` | Cambodian arms dealers |
| `Criminals_KiuVongsa` | Criminal group in Kiu Vongsa |
| `Criminals_NamThaven` | Criminal group in Nam Thaven |
| `Criminals_POI` | Criminal group at POI locations |
| `Criminals_PhaLang` | Criminal group in Pha Lang |
| `FactionGuardMortar` | Faction guards with mortars |
| `FactionCamp` (DT_FactionCamps) | Faction camp definitions |

### 3. Weapons & Equipment (5,500+ references)

All weapon categories confirmed:
- Rifles (AR, DMR, Sniper)
- Shotguns (Pump, Semi-auto)
- Pistols
- Melee weapons
- Attachments (barrels, stocks, magazines, scopes, grips)

Confirmed calibers: 5.56×45, 7.62×39, 7.62×51 (.308), 9×19, 12 Gauge, .300 BLK, 5.7×28

Ammo types: FMJ, HP, AP, Tracer, Subsonic, Buckshot, Slug

### 4. Armor (1,700+ references)

Notable armor variants:
- `Armor_6b45Ratnik` (Russian Ratnik vest — multiple colors)
- `Armor_Jpc20` (JPC 2.0)
- `Armor_Lancer` (Lancer systems)
- `Armor_ChestRig901Elite4` (Chest rig)
- `Armor_ModularOperatorCarrierGenII` (Modular carrier)
- `Armor_Cgpc3Tqs` (CGPC platform)
- Plate carriers, chest rigs, helmets

### 5. DataTables (35 assets)

Key DataTable assets that would contain numerical game data:
- `DT_Factions` — Faction definitions
- `DT_FactionCamps` — Faction camp definitions
- `DT_AIRoles` — AI behavior roles
- `DT_AIRoleOverride` — AI role overrides
- `DT_CountryOrigins` — Character origin countries
- `DT_BodyTypeTags` — Body type tags
- `DT_FTUEQuestTags` — First-time user experience quest tags
- `DT_AdditionalGameplayTags` — Extra gameplay tags

### 6. Plugins & SDKs

| Plugin/SDK | Purpose |
|---|---|
| **Nakama SDK** (nakama-sdk.dll) | Game backend — auth, matchmaking, server list |
| **Odin SDK** (odin.dll) | Voice chat (TeamSpeak technology) |
| **AntidoteSDK** (antidote.dll) | Anti-tamper / anti-cheat |
| **Skalla** (Custom) | Madfinger's own animation library |
| **EOS SDK** (EOSSDK-Win64-Shipping.dll) | Epic Online Services |
| **AnyBrain** (anybrainSDK.dll) | AI middleware |
| **Boost** (various) | C++ standard library extensions |

### 7. Game Version Info

```
Version:       0.4.6.0
Branch:        FTW+Release-0.4.6.0-FTUE
Changelist:    270156
Build Agent:   D:\HordeAgent\GZW_Rel04\Sync\ (UE5 Horde build)
Build Date:    July 3-4, 2026
```

---

## Tools Provided

### MCP Servers (for use with OpenCode)

| Server | Purpose |
|---|---|
| `re-agent-mcp-server.py` | auto-re-agent integration with OpenCode GO |
| `ue5-pak-mcp-server.py` | UE5 PAK file exploration (file listing) |
| `gzw-pak-mcp-server.py` | GZW-specific PAK data queries |

### Custom Scripts

| Script | Location |
|---|---|
| `code_analysis/extract_strings.py` | Extract all strings from binaries |
| `pak_data/read_utoc.py` | Parse UE5 UTOC format |
| `pak_data/parse_utoc.py` | Advanced UTOC parsing |
| `pak_data/find_aes_key.py` | Search for AES encryption keys |

---

## What's Missing

These require either FModel working with GZW's custom UE5 format or memory reading:

- **Weapon stats** (damage, fire rate, accuracy, recoil)
- **Armor values** (protection levels by material/class)
- **Spawn tables** (loot placement, enemy spawns)
- **Trading prices** (item costs at vendors)
- **Quest requirements & rewards** (numerical values)
- **Skill progression** (XP curves, skill effects)
- **Health/medical values** (bleed rates, healing amounts)

FModel 4.4.4.0 and dec-2025 are available in the `tools/` directory if future updates add GZW support.

---

## Credits

- Extracted by Byte (OpenCode AI agent)
- Tools: FModel, Python, Ghidra 12.1.2
- Game: Gray Zone Warfare by Madfinger Games / Team FTW
