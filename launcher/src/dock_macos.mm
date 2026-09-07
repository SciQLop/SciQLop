#include "dock.hpp"

#import <AppKit/AppKit.h>

namespace dock {
void set_visible(bool visible) {
    [NSApp setActivationPolicy:visible ? NSApplicationActivationPolicyRegular
                                       : NSApplicationActivationPolicyAccessory];
}
}
