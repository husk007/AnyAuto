# AnyAuto + Shizuku: Android 16 / MediaTek UserService crash

## TL;DR — verified workaround on a real device

**Device:** Xiaomi 13T Pro (MediaTek), Android 16 / HyperOS, no root; Shizuku launched through wireless debugging; AnyAuto package `com.mag.anyauto`.

**Failing setup:** Shizuku 13.6.0: AnyAuto remains on “Connecting to Shizuku…”; its **Try** preview cannot launch.

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
