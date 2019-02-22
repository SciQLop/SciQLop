include(sciqlop_tests)
subdirs(GUITestUtils)
declare_test(simple_graph simple_graph simple_graph/main.cpp "sciqlopgui;TestUtils;GUITestUtils;Qt5::Test")
declare_test(multiple_sync_graph multiple_sync_graph multiple_sync_graph/main.cpp "sciqlopgui;TestUtils;GUITestUtils;Qt5::Test")

declare_manual_test(event_list event_list catalogue/event_list/main.cpp "sciqlopgui;TestUtils;GUITestUtils;Qt5::Test")
declare_manual_test(repository_list repository_list catalogue/repository_list/main.cpp "sciqlopgui;TestUtils;GUITestUtils;Qt5::Test")
