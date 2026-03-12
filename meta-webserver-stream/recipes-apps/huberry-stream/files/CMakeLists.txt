cmake_minimum_required(VERSION 3.15)
project(WebServerVideoPlayer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(fmt REQUIRED)

find_library(MPV_LIBRARIES NAMES mpv)
find_path(MPV_INCLUDE_DIRS mpv/client.h)
if(NOT MPV_LIBRARIES OR NOT MPV_INCLUDE_DIRS)
    message(FATAL_ERROR "libmpv not found in sysroot")
endif()

add_executable(wserVideoPlayer main.cpp)

target_include_directories(wserVideoPlayer PRIVATE ${MPV_INCLUDE_DIRS})

target_link_libraries(wserVideoPlayer PRIVATE fmt::fmt ${MPV_LIBRARIES})

install(TARGETS wserVideoPlayer
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
