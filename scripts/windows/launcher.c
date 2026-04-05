/* Tiny MSIX entry-point launcher for SciQLop.
 *
 * Sets the environment variables that the bundled app expects
 * (SCIQLOP_BUNDLED, PATH with node/uv, SSL certs) then execs
 * python.exe -m SciQLop.app, forwarding all arguments.
 *
 * Compiled on CI with: cl /Fe:SciQLop.exe launcher.c
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                    LPWSTR lpCmdLine, int nCmdShow) {
    (void)hInstance; (void)hPrevInstance; (void)lpCmdLine; (void)nCmdShow;

    wchar_t exe_path[MAX_PATH];
    GetModuleFileNameW(NULL, exe_path, MAX_PATH);

    /* Strip filename to get the package root directory */
    wchar_t *last_sep = wcsrchr(exe_path, L'\\');
    if (last_sep) *last_sep = L'\0';
    wchar_t *root = exe_path;

    /* Build paths */
    wchar_t python_path[MAX_PATH];
    wchar_t node_path[MAX_PATH];
    wchar_t uv_path[MAX_PATH];
    wchar_t certifi_cmd[MAX_PATH];

    _snwprintf(python_path, MAX_PATH, L"%s\\python", root);
    _snwprintf(node_path, MAX_PATH, L"%s\\node", root);
    _snwprintf(uv_path, MAX_PATH, L"%s\\uv", root);

    /* Set SCIQLOP_BUNDLED */
    SetEnvironmentVariableW(L"SCIQLOP_BUNDLED", L"1");

    /* Prepend node and uv to PATH */
    wchar_t old_path[32767];
    GetEnvironmentVariableW(L"PATH", old_path, 32767);
    wchar_t new_path[32767];
    _snwprintf(new_path, 32767, L"%s;%s;%s\\Scripts;%s",
               node_path, uv_path, python_path, old_path);
    SetEnvironmentVariableW(L"PATH", new_path);

    /* Resolve SSL_CERT_FILE via certifi (best-effort) */
    _snwprintf(certifi_cmd, MAX_PATH, L"%s\\python.exe", python_path);

    /* Launch python -m SciQLop.app */
    wchar_t cmd[32767];
    _snwprintf(cmd, 32767, L"\"%s\\python.exe\" -m SciQLop.app %s",
               python_path, lpCmdLine);

    STARTUPINFOW si = { .cb = sizeof(si) };
    PROCESS_INFORMATION pi;

    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        MessageBoxW(NULL, L"Failed to start SciQLop", L"Error", MB_OK | MB_ICONERROR);
        return 1;
    }

    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exit_code;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return (int)exit_code;
}
