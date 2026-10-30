"""Exercise the Mac front end's real display-sleep activity without opening a window."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('clang'), 'requires macOS and clang')
class MacDisplaySleep(unittest.TestCase):
    def test_focused_window_holds_and_releases_display_assertion(self):
        source = (REPO / 'dm/host/front_mac.m').read_text()
        start = source.index('static id g_display_activity;')
        end = source.index('static int g_mouse_down;', start)
        code = source[start:end]
        harness = r'''
#import <Foundation/Foundation.h>
#import <IOKit/pwr_mgt/IOPMLib.h>
#include <assert.h>
#include <unistd.h>
static int display_assertions(void) {
    CFDictionaryRef all = NULL;
    assert(IOPMCopyAssertionsByProcess(&all) == kIOReturnSuccess);
    NSDictionary *processes = CFBridgingRelease(all);
    int count = 0;
    for (NSDictionary *entry in processes[@(getpid())]) {
        if ([entry[(__bridge NSString *)kIOPMAssertionTypeKey] isEqualToString:(__bridge NSString *)kIOPMAssertionTypePreventUserIdleDisplaySleep] &&
            [entry[(__bridge NSString *)kIOPMAssertionLevelKey] intValue] == kIOPMAssertionLevelOn) count++;
    }
    return count;
}
'''
        checks = r'''
int main(void) { @autoreleasepool {
    int baseline = display_assertions();
    display_sleep_active(0); assert(!g_display_activity);
    display_sleep_active(1); assert(g_display_activity);
    id first = g_display_activity;
    assert(display_assertions() > baseline);
    display_sleep_active(1); assert(g_display_activity == first);
    display_sleep_active(0); assert(!g_display_activity);
    assert(display_assertions() == baseline);
    display_sleep_active(0); assert(display_assertions() == baseline);
    display_sleep_active(1); assert(display_assertions() > baseline);
    display_sleep_active(0); assert(display_assertions() == baseline);
} return 0; }
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sleep.m').write_text(harness + code + checks)
            build = subprocess.run(['clang', '-fobjc-arc', '-Wall', '-Wextra', '-Werror',
                                    '-framework', 'Foundation', '-framework', 'IOKit',
                                    str(root / 'sleep.m'), '-o', str(root / 'sleep')],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(root / 'sleep')], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_activity_follows_window_input_focus(self):
        source = (REPO / 'dm/host/front_mac.m').read_text()
        release = source[source.index('static void input_release(void)'):source.index('static void input_resume(void)')]
        resume = source[source.index('static void input_resume(void)'):source.index('static void pads_start(void)')]
        self.assertIn('display_sleep_active(0);', release)
        self.assertIn('display_sleep_active(1);', resume)
        self.assertIn('display_sleep_active(win.isKeyWindow);', source)


if __name__ == '__main__':
    unittest.main()
