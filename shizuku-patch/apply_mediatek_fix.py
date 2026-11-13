#!/usr/bin/env python3
"""Patch pinned Shizuku 13.6.0 sources for MediaTek UserService startup.

Based on RikkaApps/Shizuku#1198 issuecomment-6008317929. The app_process
helper has no ActivityThread.mBoundApplication; affected OEM frameworks
call Application.getProcessName().equals(...) and crash with NPE.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_mediatek_fix.py <Shizuku source root>")

root = Path(sys.argv[1])
target = root / "api/server-shared/src/main/java/rikka/shizuku/server/UserService.java"
source = target.read_text(encoding="utf-8")

before = """            Method makeApplication = loadedApk.getClass().getDeclaredMethod("makeApplication", boolean.class, Instrumentation.class);
            Application application = (Application) makeApplication.invoke(loadedApk, true, null);"""

after = """            // MediaTek/OEM compatibility (Shizuku#1198): this helper runs via
            // app_process, not ActivityThread.bindApplication(). Some OEM
            // LoadedApk builds call Application.getProcessName().equals(...)
            // even when the process name is null. Populate AppBindData first.
            try {
                Class<?> bindDataClass = Class.forName("android.app.ActivityThread$AppBindData");
                Constructor<?> bindDataConstructor = bindDataClass.getDeclaredConstructor();
                bindDataConstructor.setAccessible(true);
                Object bindData = bindDataConstructor.newInstance();

                Field processNameField = bindDataClass.getDeclaredField("processName");
                processNameField.setAccessible(true);
                // Avoid running OEM resource preload meant for real app processes.
                processNameField.set(bindData, name != null ? name : pkg + ":user_service");

                Field appInfoField = bindDataClass.getDeclaredField("appInfo");
                appInfoField.setAccessible(true);
                // Also prevents ActivityThread.currentPackageName() from NPE.
                appInfoField.set(bindData, new ApplicationInfo());

                Field boundApplicationField = ActivityThread.class.getDeclaredField("mBoundApplication");
                boundApplicationField.setAccessible(true);
                if (boundApplicationField.get(activityThread) == null) {
                    boundApplicationField.set(activityThread, bindData);
                    Log.i(TAG, "initialized ActivityThread process state for OEM compatibility");
                }
            } catch (Throwable compatibilityError) {
                Log.w(TAG, "unable to initialize OEM process state", compatibilityError);
            }

            Method makeApplication = loadedApk.getClass().getDeclaredMethod("makeApplication", boolean.class, Instrumentation.class);
            Application application = (Application) makeApplication.invoke(loadedApk, true, null);"""

if source.count(before) != 1:
    raise SystemExit("ABORT: Shizuku 13.6.0 UserService snippet was not found once")
old_import = "import android.content.ContextHidden;\n"
if source.count(old_import) != 1:
    raise SystemExit("ABORT: expected import section missing")
source = source.replace(old_import, old_import + "import android.content.pm.ApplicationInfo;\n")
source = source.replace(before, after)
target.write_text(source, encoding="utf-8")

gradle = root / "build.gradle"
text = gradle.read_text(encoding="utf-8")
count_line = "def gitCommitCount = Integer.parseInt('git rev-list --count HEAD'.execute([], project.rootDir).text.trim())"
name_line = 'versionName = "${baseVersionName}.r${gitCommitCount}.${gitCommitId}"'
if text.count(count_line) != 1 or text.count(name_line) != 1:
    raise SystemExit("ABORT: unexpected Shizuku v13.6.0 build.gradle")
text = text.replace(count_line, "def gitCommitCount = 1086 // original Shizuku 13.6.0 version code")
text = text.replace(name_line, 'versionName = "${baseVersionName}.r${gitCommitCount}.${gitCommitId}-mtkfix1-unofficial"')
gradle.write_text(text, encoding="utf-8")

print("PATCHED", target)
print("PATCHED", gradle)
print("Signing: disposable debug/test key, never the original Shizuku release key.")
