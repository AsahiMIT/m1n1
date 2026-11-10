// SPDX-License-Identifier: MIT
#![allow(dead_code)]

use versions::versions;

#[versions(AGX)]
#[repr(C)]
struct Mixed {
    prefix: u32,
    #[ver(G == G13 && V == V12_4 || G == G14)]
    value: u32,
}

#[versions(AGX)]
#[repr(C)]
struct Grouped {
    prefix: u32,
    #[ver((G == G13 && V == V12_4) || G == G14)]
    value: u32,
}

#[versions(AGX)]
#[repr(C)]
struct ExistingCondition {
    prefix: u32,
    #[ver((G >= G14X && V < V13_3) || (G <= G14 && V >= V13_3))]
    value: u32,
}

#[test]
fn and_binds_more_tightly_than_or() {
    assert_eq!(size_of::<MixedG13V12_3>(), 4);
    assert_eq!(size_of::<MixedG14V12_4>(), 8);
    assert_eq!(size_of::<MixedG13V13_5>(), 4);
    assert_eq!(size_of::<MixedG14V13_5>(), 8);
    assert_eq!(size_of::<MixedG14XV13_5>(), 4);
}

#[test]
fn explicit_grouping_has_the_same_layout() {
    assert_eq!(size_of::<GroupedG13V12_3>(), 4);
    assert_eq!(size_of::<GroupedG14V12_4>(), 8);
    assert_eq!(size_of::<GroupedG13V13_5>(), 4);
    assert_eq!(size_of::<GroupedG14V13_5>(), 8);
    assert_eq!(size_of::<GroupedG14XV13_5>(), 4);
}

#[test]
fn retained_driver_condition_keeps_its_layout() {
    assert_eq!(size_of::<ExistingConditionG13V12_3>(), 4);
    assert_eq!(size_of::<ExistingConditionG14V12_4>(), 4);
    assert_eq!(size_of::<ExistingConditionG13V13_5>(), 8);
    assert_eq!(size_of::<ExistingConditionG14V13_5>(), 8);
    assert_eq!(size_of::<ExistingConditionG14XV13_5>(), 4);
}
