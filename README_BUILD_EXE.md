# NOTZYH Optimizer — Standalone EXE builder

This package lets GitHub Actions build `NOTZYH_Optimizer.exe` on a Windows runner.
You do **not** need to install Python on your own Windows PC to run the resulting EXE.

## Build the EXE (one-time setup)
1. Sign in to GitHub and create a new repository.
2. Upload the contents of this folder to the repository, keeping the `.github/workflows/build-windows-exe.yml` path intact.
3. Open the repository's **Actions** tab.
4. Select **Build NOTZYH Optimizer for Windows**.
5. Click **Run workflow**.
6. When the run finishes successfully, open that run and download the artifact named `NOTZYH_Optimizer_Windows10`.
7. Extract the downloaded artifact. It contains `NOTZYH_Optimizer.exe`.

## Run
On your Windows 10 PC, right-click `NOTZYH_Optimizer.exe` and select **Run as administrator** when applying or restoring settings.

## Important
- This workflow builds the EXE remotely on a Windows machine. The resulting EXE does not require Python to be installed on your PC.
- Windows may show a SmartScreen warning because this is an unsigned, self-built application. Only run software you built or trust.
- The app still makes only its documented, reversible changes. It does not bulk-disable Windows services.
