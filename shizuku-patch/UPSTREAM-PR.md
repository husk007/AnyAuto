# Fix UserService startup on MediaTek / HyperOS when LoadedApk.makeApplication() requires a bound process

## Summary

Shizuku **13.6.0 (r1086)** fails to start **UserService** processes on some MediaTek Android builds. Shizuku itself runs, clients have permission and receive the Shizuku binder, but the helper process crashes before loading the user's service.

This patch initializes `ActivityThread.mBoundApplication` with a minimal `AppBindData` containing a non-null `processName` and `appInfo` before the reflective `LoadedApk.makeApplication()` call. It is intentionally restricted to the `UserService.create()` initialization path and falls back to the existing behavior when the OEM-specific fields are unavailable.

The exact patch was compiled into an unofficial Shizuku 13.6.0 APK and **confirmed working by a real user on Xiaomi 13T Pro / MediaTek / Android 16 / HyperOS**. This is a user-reported successful field test, not a maintainer or CI device-farm test.

## Root cause

In Shizuku 13.5.4, `UserService.create()` constructs the service directly from `context.getClassLoader()`. In 13.6.0, it calls `LoadedApk.makeApplication(true, null)` first. The helper process runs with `app_process`, not the normal `ActivityThread.bindApplication()` lifecycle. On affected OEM frameworks, `ActivityThread.mBoundApplication` remains null; `Application.getProcessName()` returns null. MediaTek's modified `LoadedApk.makeApplicationInner()` can call `Application.getProcessName().equals(mPackageName)` without checking for null, leading to an NPE.

The `mInitialApplication` field is assigned *after* `makeApplication()` in Shizuku 13.6.0, too late to prevent this crash.

## Confirmed device / reproduction

| Item | Value |
| --- | --- |
| Phone | **Xiaomi 13T Pro** (MediaTek Dimensity series) |
| OS | **Android 16 / Xiaomi HyperOS** |
| Privilege mode | Shizuku started with **wireless debugging / ADB**, **no root** |
| Client | **AnyAuto**, package `com.mag.anyauto`, `DisplayService` user service |
| Official Shizuku 13.6.0 | **FAIL**, binder and authorization OK, UserService starter exits with code 1; screen stays "Connecting to Shizuku..." |
| Official Shizuku 13.5.4 | **PASS**, AnyAuto `Try` works |
| **Patched Shizuku 13.6.0** | **PASS**, user confirmed AnyAuto `Try` works ("Działa super") after installing patched APK on the same phone |
| Car head-unit Android Auto | Not separately established by this report |

Relevant log lines from the unpatched 13.6.0 on 2026-11-13:

```text
22:50:16.018 I/AnyAuto: binding Shizuku display service (attempt 1/3)
22:50:16.021 I/UserServiceManager: New service record com.mag.anyauto:com.mag.anyauto.DisplayService: version=14, daemon=false
22:50:16.573 D/AndroidRuntime: Calling main entry moe.shizuku.starter.ServiceStarter
22:50:16.589 I/ShizukuServiceStarter: starting service com.mag.anyauto/com.mag.anyauto.DisplayService...
22:50:16.789 W/ShizukuServiceStarter: unable to start service com.mag.anyauto/com.mag.anyauto.DisplayService...
22:50:16.789 W/ShizukuServiceStarter: java.lang.reflect.InvocationTargetException
22:50:16.789 W/ShizukuServiceStarter: Caused by: java.lang.NullPointerException: Attempt to invoke virtual method 'boolean java.lang.Object.equals(java.lang.Object)' on a null object reference
22:50:16.789 W/ShizukuServiceStarter: at android.app.LoadedApk.makeApplicationInner(LoadedApk.java:1605)
22:50:16.789 W/ShizukuServiceStarter: at android.app.LoadedApk.makeApplication(LoadedApk.java:1495)
22:50:16.789 I/AndroidRuntime: VM exiting with result code 1
22:50:46.053 W/UserServiceRecord: Service record ... is not started in 30000 ms
```

## Technical details of the patch

- Reflectively construct `android.app.ActivityThread$AppBindData` in `UserService.create()`.
- Set `processName` to `pkg + ":user_service"` (or the provided debug name). Keep it different from the package so OEM resource-preload logic for real app processes does not run.
- Set `appInfo` to a non-null `ApplicationInfo`; without it, `ActivityThread.currentPackageName()` can throw a second NPE.
- If `ActivityThread.mBoundApplication` is null, populate it before calling `makeApplication()`.
- Log a warning and preserve the original startup path if this reflective compatibility step cannot run.
- Do not change UserService API, binder communications, or actual client `DisplayService` constructors.

## Validation

1. **Built from tag `RikkaApps/Shizuku@v13.6.0`** with pinned submodule `Shizuku-API@510fc988`; the patch was applied to `server-shared/src/main/java/rikka/shizuku/server/UserService.java`.
2. **GitHub Actions release build passed:** `./gradlew :manager:assembleRelease`; SDK 36, Java 21, compiled successfully. The locally signed APK passed `apksigner verify` (v2 signature), versionCode 1086, versionName `13.6.0.r1086.2650830-mtkfix1-unofficial`. CI: https://github.com/husk007/AnyAuto/actions/runs/43525961855
3. **Real-world A/B test confirmed by the Xiaomi owner:** official 13.6.0 fails, 13.5.4 works, and patched 13.6.0 works with AnyAuto Try. No further changes to AnyAuto were reported as part of this test.
4. Not yet tested on other Android versions, OEMs, or the in-car Android Auto head unit.

## Related issues

- RikkaApps/Shizuku#1198 — MediaTek UserService startup crash / process-name null
- RikkaApps/Shizuku#1171 — matching `LoadedApk` null process-name disassembly
- RikkaApps/Shizuku#2561 — Android 16 startup failure
- RikkaApps/Shizuku#2048 — regression from 13.5.4 to 13.6.0
- The compatibility strategy was previously reported and independently tested on a different MediaTek Android 16 device in https://github.com/RikkaApps/Shizuku/issues/1198#issuecomment-6008317929

## Source code / reproducibility

- **Upstream-ready source patch:** https://github.com/husk007/AnyAuto/blob/build/shizuku-1360-mtk-fix/shizuku-patch/Shizuku-API-MediaTek-UserService.patch
- Reproducible build and signing workflow: https://github.com/husk007/AnyAuto/blob/build/shizuku-1360-mtk-fix/.github/workflows/shizuku-mtk.yml
- Full diagnostic report: https://github.com/husk007/AnyAuto/blob/fix/mediatek-shizuku-userservice-guidance/docs/shizuku-mediatek-android16.md

**Note:** this change targets **RikkaApps/Shizuku-API**, where the `UserService.java` implementation is maintained. To ship it in Shizuku, the main Shizuku repository must also update its Shizuku-API submodule revision after the fix merges.

Please review compatibility of `ActivityThread.AppBindData` reflection on non-MediaTek devices; the patch catches reflective failures but cannot protect against every possible OEM framework behavior.
