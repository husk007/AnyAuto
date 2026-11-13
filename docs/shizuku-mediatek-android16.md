# AnyAuto + Shizuku: Android 16 / MediaTek UserService crash

## TL;DR — verified workaround on a real device

**Device:** Xiaomi 13T Pro (MediaTek), Android 16 / HyperOS, no root; Shizuku launched through wireless debugging; AnyAuto package `com.mag.anyauto`.

**Failing setup:** Shizuku 13.6.0: AnyAuto remains on “Connecting to Shizuku…”; its **Try** preview cannot launch. **Source-level regression identified:** Shizuku 13.6.0 added `LoadedApk.makeApplication()` inside `UserService.create()`, whereas 13.5.4 loaded the service class from the package `Context` without creating the app `Application`. On affected MediaTek frameworks, the new call executes an OEM `Application.getProcessName().equals(...)` check with a null process name. Details and upstream-tested patch below.

**Working setup (confirmed by the device owner, 2026-11-13):** downgrade Shizuku to **13.5.4**, restart it using wireless debugging, and reauthorize AnyAuto. **Try works end-to-end**: the user successfully wrote a ChatGPT message through the Try screen. Android Auto in-car operation has **not yet been tested**. This is a confirmed workaround on this device, not a universal guarantee.

Official release: https://github.com/RikkaApps/Shizuku/releases/tag/v13.5.4

Downgrading may require uninstalling the newer Shizuku, which can reset its configuration and permissions for *all* Shizuku-dependent apps. Back up relevant settings and be prepared to grant permissions again. Only use official releases. Shizuku 13.5.4 is older and may lack newer fixes; assess the tradeoff.

## Exact evidence — failure with Shizuku 13.6.0

Extracted from the user's `logcat` capture on 2026-11-13 (timestamps and PIDs retained):

```text
11-13 22:50:15.926 D/ShizukuProvider(27725): Initialize Sui: false
11-13 22:50:15.935 D/ShizukuProvider(27725): binder received
11-13 22:50:15.935 D/ShizukuProvider(27725): sendBinder is called when already a living binder
11-13 22:50:15.936 I/ShizukuApplication(27725): attachApplication
11-13 22:50:16.018 I/AnyAuto (27725): binding Shizuku display service (attempt 1/3)
11-13 22:50:16.021 I/UserServiceManager(12181): New service record com.mag.anyauto:com.mag.anyauto.DisplayService (be72b787-c94f-4d81-961a-94ea30ccb579-1794606616021): version=14, daemon=false, apk=/data/app/.../base.apk
11-13 22:50:16.021 V/UserServiceRecord(12181): Set starting timeout for service record be72b787-c94f-4d81-961a-94ea30ccb579-1794606616021: 30000
11-13 22:50:16.022 V/UserServiceManager(12181): Starting process for service record com.mag.anyauto:com.mag.anyauto.DisplayService (be72b787-c94f-4d81-961a-94ea30ccb579-1794606616021)...
11-13 22:50:16.252 D/AndroidRuntime(20499): >>>>>> START com.android.internal.os.RuntimeInit uid 2000 <<<<<<
11-13 22:50:16.573 D/AndroidRuntime(20499): Calling main entry moe.shizuku.starter.ServiceStarter
11-13 22:50:16.589 I/ShizukuServiceStarter(20499): starting service com.mag.anyauto/com.mag.anyauto.DisplayService...
11-13 22:50:16.789 W/ShizukuServiceStarter(20499): unable to start service com.mag.anyauto/com.mag.anyauto.DisplayService...
11-13 22:50:16.789 W/ShizukuServiceStarter(20499): java.lang.reflect.InvocationTargetException
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      at java.lang.reflect.Method.invoke(Native Method)
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      at rikka.shizuku.Vr.a(SourceFile:209)
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      at moe.shizuku.starter.ServiceStarter.main(SourceFile:14)
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      at com.android.internal.os.RuntimeInit.nativeFinishInit(Native Method)
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      at com.android.internal.os.RuntimeInit.main(RuntimeInit.java:394)
11-13 22:50:16.789 W/ShizukuServiceStarter(20499): Caused by: java.lang.NullPointerException: Attempt to invoke virtual method 'boolean java.lang.Object.equals(java.lang.Object)' on a null object reference
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      at android.app.LoadedApk.makeApplicationInner(LoadedApk.java:1605)
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      at android.app.LoadedApk.makeApplication(LoadedApk.java:1495)
11-13 22:50:16.789 W/ShizukuServiceStarter(20499):      ... 5 more
11-13 22:50:16.789 I/AndroidRuntime(20499): VM exiting with result code 1.
11-13 22:50:46.053 W/UserServiceRecord(12181): Service record be72b787-c94f-4d81-961a-94ea30ccb579-1794606616021 is not started in 30000 ms
```

The APK path is abbreviated here for privacy/readability. These are **selected log lines**, not a complete raw log file.

Additional observed events:

```text
11-13 22:50:16.059 W/ActivityManager(1937): Permission Denial: getCurrentUser() from pid=27725, uid=10759 requires android.permission.INTERACT_ACROSS_USERS
11-13 22:50:16.586 E/BoostFramework(20499): java.lang.ClassNotFoundException: com.qualcomm.qti.Performance
11-13 22:50:27.043 W/FinalizerDaemon(27725): avc: denied { getopt } for path="/dev/socket/usap_pool_primary" ... app=com.mag.anyauto
```

These are **not proven causal**: the decisive exception is the `LoadedApk.makeApplicationInner` null dereference in the separate Shizuku starter process (PID 20499). In particular, the Qualcomm performance class warning is common on a MediaTek phone and does not establish an AnyAuto dependency failure.

## Causal chain and confidence

1. **Confirmed:** Android starts AnyAuto's `MainActivity`; Shizuku provider receives a live binder and attaches the app; Shizuku permission `moe.shizuku.manager.permission.API_V23` was previously checked as granted.
2. **Confirmed:** `Shell.connect()` calls `Shizuku.bindUserService` for `com.mag.anyauto.DisplayService`, version 14.
3. **Confirmed:** Shizuku starts a shell-UID (`2000`) helper process, but `ServiceStarter` throws during `LoadedApk.makeApplication()` and exits with code 1 **before it can deliver the service binder**.
4. **Confirmed:** Shizuku waits 30 seconds, then reports the service was not started; AnyAuto remains in CONNECTING.
5. **Confirmed:** Changing Shizuku to 13.5.4 restores working Try behavior on the same phone. The user did not report changing AnyAuto's code as part of this successful test.
6. **Inference, not proved by this stack trace alone:** an OEM-specific `LoadedApk` implementation and Shizuku's process initialization interact badly in 13.6.0. The exact null variable cannot be determined from the stack trace alone.

The existing AnyAuto branch `fix/shizuku-user-service-timeout` adds a 35-second timeout and up to 3 attempts. **Those retries cannot fix a deterministic crash inside Shizuku's starter**; they only make failed binds visible and may recover intermittent failures. The existing `DisplayService(Context)` and no-argument constructors are not reached, so changing them is not an evidence-based fix.

## Reproduce and diagnose (ADB shell / Termux + Shizuku rish)

```sh
logcat -c
am force-stop com.mag.anyauto
am start -n com.mag.anyauto/.MainActivity
sleep 40
logcat -d -v time -b main,system,crash > /sdcard/Download/anyauto-debug.log
grep -iE 'ShizukuServiceStarter|UserServiceManager|UserServiceRecord|LoadedApk|AnyAuto|AndroidRuntime|FATAL EXCEPTION' /sdcard/Download/anyauto-debug.log | tail -n 100
```

The log is collected **after the app is launched**; if the service binds only when Try is pressed, press Try during the 40-second capture window. The user captured the critical stack trace using a filter containing `ShizukuServiceStarter` — filtering only on `com.mag.anyauto` misses it because the crash is logged under Shizuku's process. Do not publish full logs without reviewing them for sensitive data.

To inspect the complete stack near the failure:

```sh
grep -n -A 18 -B 5 'unable to start service com.mag.anyauto' /sdcard/Download/anyauto-debug.log
```

## Precise source-code regression (investigated 2026-11-14)

This is **not a failure in AnyAuto's `DisplayService` constructor**. Comparison of the exact Shizuku release trees confirms the behavioral change was introduced by the Shizuku-API submodule:

- Shizuku **13.5.4** uses Shizuku-API commit [`01e08879`](https://github.com/RikkaApps/Shizuku-API/blob/01e08879d58a5cb11a333535c6ddce9f7b7c88ff/server-shared/src/main/java/rikka/shizuku/server/UserService.java#L56-L79): `ActivityThread.systemMain()` → `createPackageContextAsUser()` → `context.getClassLoader()` → construct service with the package `Context`.
- Shizuku **13.6.0** uses Shizuku-API commit [`510fc988`](https://github.com/RikkaApps/Shizuku-API/blob/510fc988c02c3475d8c25db170f96792f105bdf8/server-shared/src/main/java/rikka/shizuku/server/UserService.java#L60-L95): after creating the package `Context`, it reflects `ContextImpl.mPackageInfo` to obtain `LoadedApk`, invokes **`LoadedApk.makeApplication(true, null)`** at line 76, and only *after the call succeeds* writes the resulting `Application` into `ActivityThread.mInitialApplication`. It then loads the service class and calls the constructor.

Relevant new Shizuku 13.6.0 code, shown minimally:

```java
Object loadedApk = mPackageInfo.get(context);
Method makeApplication = loadedApk.getClass()
    .getDeclaredMethod("makeApplication", boolean.class, Instrumentation.class);
Application application = (Application) makeApplication.invoke(loadedApk, true, null); // throws on affected device
```

**Mechanism (strongly supported by OEM framework analysis on other affected MediaTek phones, but this Xiaomi's `framework.jar` has not been disassembled):**

1. The Shizuku `UserService` helper runs via [`/system/bin/app_process`](https://github.com/RikkaApps/Shizuku/blob/v13.6.0/server/src/main/java/rikka/shizuku/server/ShizukuUserServiceManager.java#L26-L39), not the ordinary Android application lifecycle. It calls `ActivityThread.systemMain()` and never binds a normal app via `ActivityThread.bindApplication()`.
2. Therefore `ActivityThread.mBoundApplication` may be null. On affected Android builds, `Application.getProcessName()` delegates to `ActivityThread.currentProcessName()`, returning null without `mBoundApplication`.
3. MediaTek/OEM modifications to `LoadedApk.makeApplicationInner()` call `Application.getProcessName().equals(mPackageName)` without a null check, leading to the exact `NullPointerException` logged in AnyAuto (`LoadedApk.java:1605`).
4. The `DdmHandleAppName.setAppName(...)` call in `UserService.create()` and the `--nice-name` flag in the `app_process` command set process *debug/display names*, not `ActivityThread.mBoundApplication`; they do not cure `Application.getProcessName()`. Setting `mInitialApplication` after `makeApplication()` is too late.
5. `UserService.create()` catches the reflection exception and returns null. [`ServiceStarter.main()`](https://github.com/RikkaApps/Shizuku/blob/v13.6.0/starter/src/main/java/moe/shizuku/starter/ServiceStarter.java#L61-L75) immediately calls `System.exit(1)`; the Shizuku server waits for a Binder until its 30-second timeout.

**Independent upstream verification of the exact failing variable and tested patch:**

- [RikkaApps/Shizuku#1171, framework disassembly](https://github.com/RikkaApps/Shizuku/issues/1171#issuecomment-2952516583): user inspected an OEM `framework.jar` and found a null `procName` at the `equals()` call.
- [RikkaApps/Shizuku#1198, framework investigation](https://github.com/RikkaApps/Shizuku/issues/1198): Xiaomi/MediaTek `Application.getProcessName()` null during UserService setup.
- [RikkaApps/Shizuku#1198, working patched Shizuku 13.6.0 test](https://github.com/RikkaApps/Shizuku/issues/1198#issuecomment-6008317929): a reporter on MediaTek Android 16 populated `ActivityThread.mBoundApplication` with `AppBindData`, setting both `processName` (non-null, intentionally distinct from the application package name) and a non-null `appInfo` before calling `makeApplication()`. They reported three successful runs after patching the official 13.6.0 APK, vs reproducible failure beforehand. This success was **not tested on the AnyAuto owner's Xiaomi**.

**AnyAuto code review:**

- [`Shell.java:85–86`](https://github.com/husk007/AnyAuto/blob/fix/shizuku-user-service-timeout/src/com/mag/anyauto/Shell.java#L81-L86) correctly requests a `UserService` for `DisplayService`; [`Shell.java:140–166`](https://github.com/husk007/AnyAuto/blob/fix/shizuku-user-service-timeout/src/com/mag/anyauto/Shell.java#L140-L166) checks binder/permission and calls `Shizuku.bindUserService()`. Both succeeded far enough for Shizuku to start `ServiceStarter`.
- [`DisplayService.java:110–117`](https://github.com/husk007/AnyAuto/blob/fix/shizuku-user-service-timeout/src/com/mag/anyauto/DisplayService.java#L110-L117) provides BOTH a `Context` constructor and a no-argument constructor. Its `ShellContext` wrapper is constructed only if this point is reached, which it never is in the failing Shizuku 13.6.0 startup.
- AnyAuto's [`tools/deps.txt:8–10`](https://github.com/husk007/AnyAuto/blob/fix/shizuku-user-service-timeout/tools/deps.txt#L8-L10) pins the **client** Shizuku API/provider to 13.1.5; these versions are independent of the separately installed Shizuku **manager/server** 13.5.4 or 13.6.0. Updating this client library alone cannot remove the server-side `LoadedApk.makeApplication()` path.
- `.processNameSuffix("display")`, `.daemon(false)`, retries, API permissions, and the app's target SDK do not initialize `mBoundApplication`; modifying them is not a causal repair.

### Repair options and priority

**Preferred Shizuku-side fix:** Before `makeApplication.invoke(...)`, initialize the missing `ActivityThread.AppBindData` process state correctly (the upstream-tested workaround initializes both `processName` and `appInfo`). The process name should not match the target app package to avoid triggering OEM resource preloading intended for real app processes. Review [the tested implementation](https://github.com/RikkaApps/Shizuku/issues/1198#issuecomment-6008317929) and validate the reflective fields on different Android versions/OEMs; writing hidden framework fields is version-sensitive and may affect process metadata.

**Alternative Shizuku compatibility fallback:** If reflective `makeApplication()` fails with the known OEM exception, use the Shizuku 13.5.4 code path: construct the service from `context.getClassLoader()` and pass `context` to its `Context` constructor. This would be compatible with AnyAuto's constructor but may be incompatible with other clients requiring a true `Application`, or with partially initialized process state; test before shipping. Do not use a blanket catch which hides unrelated application startup errors.

**AnyAuto-side mitigation only:** Detect repeated UserService startup failure and display the actionable Shizuku version guidance. An actual standalone AnyAuto workaround would require avoiding Shizuku's UserService starter entirely, via a separately tested alternative shell/Binder transport. Changing the constructor, service version, delays, or app manifest alone cannot avoid a `makeApplication()` call which fails **before the class is loaded**.

**Status:** This report identifies the code-level regression and a community-tested upstream patch; it does not claim an upstream Shizuku fix was merged or an AnyAuto code workaround was implemented.


## Guidance for maintainers and possible fixes

**User-facing detection:** `Shell.state()` currently returns CONNECTING for a live Shizuku binder with granted permission, even when a UserService repeatedly crashes. After failed binds, show a diagnostic state (not infinite “Connecting…”) with a link to this troubleshooting page and clear advice to check Shizuku version and Android/SoC. Never silently downgrade another app.

**AnyAuto fallback:** investigate a Shizuku-supported alternative shell-process transport (e.g., remote process API, subject to actual server compatibility) which does not use the failing `UserService` startup path. Preserve the `IDisplayService` binder interface, `Surface` parceling, virtual-display flags, lifecycle cleanup, shell UID and permission boundaries. This is a **proposal**, not implemented or validated.

**Shizuku upstream:** inspect differences between 13.5.4 and 13.6.0 in `ServiceStarter` and application/process initialization; reproduce on MediaTek/HyperOS Android 16; identify what is null at the device-specific `LoadedApk.java:1605`. Avoid assuming the AOSP line number maps exactly to this OEM framework.

Related upstream reports for investigation (similar symptoms, not independently verified as identical root cause):

- https://github.com/RikkaApps/Shizuku/issues/1198
- https://github.com/RikkaApps/Shizuku/issues/2561
- https://github.com/RikkaApps/Shizuku/issues/2048
- https://github.com/RikkaApps/Shizuku/issues/2633

## Test matrix

| Device | Android | Shizuku | AnyAuto result | Evidence |
| --- | --- | --- | --- | --- |
| Xiaomi 13T Pro / MediaTek | 16 / HyperOS | 13.6.0 | FAIL: Shizuku UserService crashes; Try unavailable | Device log above |
| Same device | 16 / HyperOS | **13.5.4** | **PASS: Try works; ChatGPT used through preview** | User-confirmed live test |
| Same device | 16 / HyperOS | 13.5.4 | **NOT TESTED: real Android Auto car display** | Pending |

This report intentionally does not claim the 13.5.4 workaround works for every Android 16 phone or that AnyAuto's in-car rendering is already validated.
