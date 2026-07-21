# Gray Zone Warfare — Reverse Engineering Technical Report

**Game:** Gray Zone Warfare (v0.4.6.0, CL-270156)
**Developer:** Madfinger Games
**Engine:** Unreal Engine 5 (custom build with Skalla animation system)
**Backend:** Nakama (Heroic Labs) + Odin VOIP + EOS
**Build Agent:** `D:\HordeAgent\GZW_Rel04\Sync\` (UE5 Horde build system)
**Build Date:** July 3–4, 2026
**Report Date:** July 21, 2026

---

## 1. Game Structure

### Executables Analyzed

| File | Size | Description |
|---|---|---|
| `GZWClientSteam-Win64-Shipping.exe` | 178 MB | Main game executable (UE5) |
| `GZWClientEAC.exe` | 3.8 MB | Easy Anti-Cheat launcher |
| `nakama-sdk.dll` | 2.0 MB | Nakama game backend SDK |
| `anybrainSDK.dll` | 9.0 MB | AI middleware |
| `odin.dll` | — | VOIP SDK (TeamSpeak Odin) |
| `antidote.dll` | — | Anti-tamper SDK |

### Plugins & SDKs Identified

| Plugin/SDK | Role |
|---|---|
| **MadfingerCoreOnline** | Nakama integration, online services |
| **MadfingerCoreServerInfo** | Server information provider |
| **Cog** | In-game developer debug console |
| **Skalla** | Custom Madfinger animation library |
| **Nakama SDK** | Game backend (auth, matchmaking, social) |
| **Odin** | Voice chat |
| **Antidote** | Anti-tamper |
| **EOS SDK** | Epic Online Services |
| **AnyBrain** | AI decision-making middleware |

---

## 2. Backend System (Nakama)

The game uses **Nakama** (open-source game backend) for all online services. The error codes and RPC names reveal the complete backend architecture:

### Character Creation

| Error Code | Description |
|---|---|
| `MFGNakama.NewCharNotWiped` | Character must be wiped before creating a new one |
| `MFGNakama.NewCharFaction` | Faction selection failed |
| `MFGNakama.NewCharUsername` | Username setting failed |
| `MFGNakama.NewCharApparel` | Clothing/appearance selection failed |
| `MFGNakama.WipeCharTooEarly` | Character wipe attempted too soon |
| `MFGNakama.WipeInternalError` | Internal wipe error |

### Name Validation

| Error Code | Description |
|---|---|
| `MFGNakama.ValidNameAlreadyExist` | Name already taken |
| `MFGNakama.ValidNameProfanity` | Profanity detected |
| `MFGNakama.ValidNameTooShort` | Name too short |
| `MFGNakama.ValidNameTooLong` | Name too long |
| `MFGNakama.ValidNameSpecialCharacters` | Special characters not allowed |

### Squad System

| Error Code | Description |
|---|---|
| `MFGNakama.SquadNotFound` | Squad does not exist |
| `MFGNakama.SquadFullSlots` | Squad is full |
| `MFGNakama.SquadSavingFailed` | Squad data save failed |
| `MFGNakama.SquadIncompatibleData` | Incompatible squad data |
| `MFGNakama.SquadUserBlockage` | User is blocked from squad |

### Custom Server System

| Code | Description |
|---|---|
| `MFGNakama.CustomServerRegionCodeNotFound` | Region code not found |
| `MFGNakama.CustomServerRegionCodeNotAllowed` | Region code not allowed |
| `MFGCreateCustomServerRequest` | Create a custom server |
| `MFGUpdateCustomServerRequest` | Update custom server config |
| `MFGListCustomServerConfigsResponse` | List available server configs |
| `MFGGetStatusCustomServerRequest` | Get server status |
| `MFGCustomServerCustomNameRequest` | Set custom server name |
| `MFGCustomServerPasswordResponse` | Password-protected server |
| `MFGChangeOwnersCustomServerRequest` | Transfer server ownership |
| `MFGPromoteMemberServerRequest` | Promote member to admin |

### Server States

```
EMFGCustomServerState::NotRunning → Starting → Running → Terminating
EMFGCustomServerPanelState::Idle → QueryingServer → ConnectedToServer
```

### Server Types

- `EMFGNakamaServerTypes::Development`
- `EMFGNakamaServerTypes::Experimental`
- `EMFGNakamaServerTypes::Production`

---

## 3. Server Features

### Server Modules (source code paths)

| Module | Source File | Function |
|---|---|---|
| MadfingerCoreOnline | `MFGCustomPlayerPersistenceService.cpp` | Player data persistence |
| MadfingerCoreServerInfo | `MFGInfoServer.cpp` | Server info endpoint |
| MadfingerGame | `MFGGameInfoServer.cpp` | Game server info |
| MadfingerGame | `MFGCustomServerClientSubsystem.cpp` | Custom server client |
| MadfingerGame | `MFGMatchmakerServerSubsystem.cpp` | Matchmaking logic |
| MadfingerGame | `MFGModerationServerSubsystem.cpp` | Moderation (kick/ban) |
| MadfingerGame | `MFGNotificationsServerSubsystem.cpp` | Push notifications |
| MadfingerGame | `MFGSquadServerSubsystem.cpp` | Squad management |
| MadfingerGame | `MFGErrorHandlingServerSubsystem.cpp` | Error handling & retry |

### Item System

| Function | Description |
|---|---|
| `Server_ItemRequestOperation` | Generic item operations |
| `Server_ItemSortingRequestOperation` | Inventory sorting |
| `AMFGPlayerController::Server_StorageRequestOperation_Implementation` | Storage/stash handling |

### Quest System

| Function | Description |
|---|---|
| `Server_AddQuestToPlayerMap` | Add quest to player |
| `Server_RemoveQuestFromPlayerMap` | Remove quest from player |
| `EMFGQuestFailureReason::LeftServer` | Quest failed — left server |
| `EMFGQuestFailureReason::LeftServerInComa` | Quest failed — left server while in coma |

### Hit Validation (Anti-Cheat)

| Result | Description |
|---|---|
| `EMFGServerHitValidationResult::Hit` | Hit registered |
| `EMFGServerHitValidationResult::DOS` | Possible DOS attack |
| `EMFGServerHitValidationResult::Invalid` | Invalid hit |
| `EMFGServerHitValidationResult::NotExist` | Target does not exist |
| `EMFGServerHitValidationResult::Wait` | Rate-limited, wait |

### Modding Support

```
AMFGPlayerController::Server_ModdingRequestOperation_Implementation
```

**Official modding support exists in the code.** This confirms the game has a modding system, which is not documented on the wiki.

### Player Operations

| Function | Description |
|---|---|
| `Server_SetProfileUpdateAtDateTime` | Update profile timestamp |
| `Server_SetTweakProfile` | Apply profile tweaks |
| `AMFGPlayerController::Server_SetRespawningInNearestCOP_Implementation` | Respawn at nearest COP |

---

## 4. Technical Details

### Game Environment

- **UE5 Storage Format:** IO Store (.ucas/.utoc) + legacy .pak
- **PAK Files:** `GZW-WindowsClient.pak` (81.6 MB container), `GZW-WindowsClient.ucas` (21.2 GB), `global.ucas` (3.1 MB)
- **Build System:** Horde (UE5 distributed build)
- **Release Tag:** `FTW+Release-0.4.6.0-FTUE-CL-270156`

### Key Bindings (from settings)

```
PushToTalk → CapsLock
WeaponCant → ThumbMouseButton2
```

### Graphics Features

- DLSS 3 (Frame Generation, Super Resolution, Reflex)
- FSR 3 (Super Resolution, Frame Generation)
- XeSS (Super Sampling)
- HDR Display Output

---

## 5. Game Assets (from UTOC Parse)

The UTOC file `GZW-WindowsClient.utoc` (27 MB) was parsed, yielding **104,826 unique strings** of which **~21,500 are game-relevant**.

### Categories

| Category | Count | Examples |
|---|---|---|
| **DataTables** | 35 | DT_Factions, DT_AIRoles, DT_CountryOrigins |
| **Weapons** | 5,543 | Rifles, shotguns, melee, attachments, ammo |
| **Armor** | 1,728 | Vests, helmets, plate carriers, chest rigs |
| **Ammunition** | 1,213 | 5.56×45, 7.62×39, 12 Gauge, .308, 9×19 |
| **Medical** | 376 | Splints, bandages, pain management, stress |
| **Keys & Keycards** | 677 | Area access, keycards |
| **Quests & Tasks** | 1,942 | Exploration, Artisan, Gunny lines |
| **Factions** | 134 | Criminal groups, arms traffickers, guards |
| **NPCs & AI** | 1,491 | AI roles, behaviors, spawns |
| **Shops & Trading** | 719 | Vendors, Gunny, Handshake |
| **Skills & Progression** | 191 | Leveling, XP, field manual |
| **Storage & Inventory** | 380 | Stashes, containers |
| **Maps & Locations** | 6,613 | Every zone, POI, building |
| **UI & Screens** | 262 | HUD, menus, widgets |

### Key DataTables

| DataTable | Likely Content |
|---|---|
| `DT_Factions` | Faction definitions and properties |
| `DT_FactionCamps` | Faction camp definitions |
| `DT_AIRoles` | AI behavior role definitions |
| `DT_AIRoleOverride` | AI role overrides |
| `DT_CountryOrigins` | Character origin countries |
| `DT_BodyTypeTags` | Body type classifications |
| `DT_FTUEQuestTags` | First-time user experience quests |
| `DT_AdditionalGameplayTags` | Extra gameplay tag definitions |

### Weapon Calibers Confirmed

- 5.56×45mm (FMJ, HP, Tracer, Subsonic)
- 7.62×39mm (FMJ, HP, AP, Tracer)
- 7.62×51mm (.308)
- 9×19mm
- 12 Gauge (Buckshot, Slug, FC Buckshot)
- .300 BLK
- 5.7×28mm

### Notable Armor Variants

- `Armor_6b45Ratnik` (Russian Ratnik — multiple color variants including Black, ThaiMercs)
- `Armor_Jpc20` (JPC 2.0)
- `Armor_Lancer` (Lancer systems)
- `Armor_ChestRig901Elite4` (Elite chest rig)
- `Armor_ModularOperatorCarrierGenII` (Modular plate carrier)
- `Armor_Cgpc3Tqs` (CGPC platform)
- `Armor_6b45Ratnik_Boss` (Boss variant)

### Factions Found

| Faction | Type |
|---|---|
| `CambodianArmsTraffickers` | Cambodian arms dealers |
| `Criminals_KiuVongsa` | Criminal faction in Kiu Vongsa |
| `Criminals_NamThaven` | Criminal faction in Nam Thaven |
| `Criminals_POI` | Criminal faction at POIs |
| `Criminals_PhaLang` | Criminal faction in Pha Lang |
| `FactionGuardMortar` | Faction guards with mortar support |

### Vendor NPCs

- `AG_Vendor_Male_Gunny` — Gunny (weapons vendor)
- `AG_Vendor_Male_Handshake` — Handshake (general/trading)
- `AG_Vendor_Male` — Generic male vendor
- Various faction-specific vendors

---

## 6. Connection & Error Handling

### Connection Errors

| Error | Description |
|---|---|
| `EMFGErrors::ConnectingToServerFailed` | Failed to connect |
| `EMFGErrors::ServerDisconnected` | Server disconnected |
| `EMFGErrors::ServerFull` | Server at capacity |
| `EMFGErrors::ServerLoginTimeout` | Login timed out |
| `EMFGErrors::ServerSteamAuthFailed` | Steam auth failed |
| `EMFGErrors::ServerVerificationFailed` | Verification failed |
| `EMFGErrors::ServerDatabaseFailed` | Server DB error |
| `EMFGErrors::ServerNakamaProfileLoadFailed` | Nakama profile load failed |

### Kick Reasons

| Error | Description |
|---|---|
| `EMFGErrors::KickedByAdminOfCustomServer` | Kicked by admin |
| `EMFGErrors::KickedByRestartingCustomServer` | Kicked — server restarting |
| `EMFGErrors::KickedByServer` | Kicked by server (generic) |
| `EMFGErrors::KickedByServerRpcViolation` | Kicked — RPC violation (cheat detection) |
| `EMFGErrors::KickedByShuttingDownCustomServer` | Kicked — server shutting down |
| `EMFGErrors::LeaveServer` | Player left server |

### EAC (Easy Anti-Cheat) Related

| Error | Description |
|---|---|
| `EMFGErrors::EAC_ServerRegistrationFailed` | EAC registration failed |
| `EMFGErrors::EAC_ServerRegistrationTimeout` | EAC registration timed out |
| `EMFGAutomaticReportCategory::EAC_ServerRegistrationTimeout` | Auto-report EAC timeout |

### Server Kick (in Coma)

```
EMFGQuestFailureReason::LeftServer       — Quest failed because player left the server
EMFGQuestFailureReason::LeftServerInComa — Quest failed because player left in coma state
```

---

## 7. Files Extracted

### Code Analysis

| File | Content |
|---|---|
| `strings/GZWClientSteam-Win64-Shipping_exe_nakama_rpcs.json` | 115 Nakama RPC error codes |
| `strings/GZWClientSteam-Win64-Shipping_exe_ue_classes.json` | 280 Unreal Engine classes |
| `strings/GZWClientSteam-Win64-Shipping_exe_config_keys.json` | 2,101 configuration keys |
| `strings/GZWClientSteam-Win64-Shipping_exe_endpoints.json` | 923 endpoint references |
| `strings/GZWClientSteam-Win64-Shipping_exe_all_strings.json` | 13,984 raw strings from main exe |
| `strings/nakama-sdk_dll_nakama_rpcs.json` | 87 Nakama RPC codes from SDK DLL |
| `strings/nakama-sdk_dll_all_strings.json` | 4,250 raw strings from Nakama SDK |

### PAK Analysis

| File | Content |
|---|---|
| `exports/GZW-WindowsClient_utoc_parsed.json` | 104,826 strings from UTOC (7 MB) |
| `exports/aes_key_candidates.json` | AES key search results (no key found — PAKs not encrypted) |

### Clean Data

| File | Content |
|---|---|
| `data/nakama_rpcs/nakama_errors.json` | Categorized Nakama RPC errors |
| `data/endpoints/server_modules.json` | Server modules, states, operations |
| `data/config/game_settings.json` | All game settings with types |

---

## 8. FModel Compatibility

**FModel cannot read GZW's PAK files.** The game uses a custom UE5 build with a modified IO Store format that FModel does not support.

**Symptoms:**
- UTOC shows as valid (98,708 files detected) but files won't load
- Error: "Could not find LoaderGlobalNameHashes chunk"
- Error: "Could not load virtual paths, plugin manifest may not exist"
- "Is Encrypted: False" — encryption is not the issue

**Attempted FModel versions:**
- ❌ dec-2025 (stable)
- ❌ 4.4.4.0 (stable)
- ❌ QA build 8b95b40
- ❌ Latest QA build 3d07a51

**UE versions tried:** UE5.2, UE5.3, UE5.4, UE5.5 — none work

**Conclusion:** GZW's custom UE5 build requires FModel update or a custom parser.

---

## 9. API Enhancement Recommendations

What was found in the game code that is **NOT on the wiki** and could enhance your API:

1. **Custom Server System** — Create, update, list, password-protect, transfer ownership, promote members (no wiki documentation exists)
2. **Squad API** — Squad RPCs and data structures
3. **Modding Support** — Direct reference in code (`Server_ModdingRequestOperation`)
4. **Hit Validation Rules** — Server-authoritative hit detection with DOS protection
5. **Quest Failure Reasons** — `LeftServer`, `LeftServerInComa`
6. **Server Maintenance States** — `MaintenanceMode`, `OutdatedClient`, `NotSupporterOwner`
7. **Faction Names** — CambodianArmsTraffickers, Criminals groups, FactionGuardMortar
8. **Vendor NPCs** — Gunny, Handshake, faction vendors
9. **DataTable Names** — 35 DataTable assets containing game balance data
10. **Bug: DT_FactionCamps appears twice** in the UTOC — may indicate duplicate or updated table
