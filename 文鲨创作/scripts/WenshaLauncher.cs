using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class WenshaLauncher
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string appDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string runApp = "";
            string probeDir = appDir;
            for (int i = 0; i < 4; i++)
            {
                string candidate = Path.Combine(probeDir, "run_app.py");
                if (File.Exists(candidate))
                {
                    appDir = probeDir;
                    runApp = candidate;
                    break;
                }
                DirectoryInfo parentInfo = Directory.GetParent(probeDir);
                if (parentInfo == null || parentInfo.FullName == probeDir)
                {
                    break;
                }
                probeDir = parentInfo.FullName;
            }

            if (!File.Exists(runApp))
            {
                MessageBox.Show("找不到 run_app.py，请把启动器放在“文鲨写作”文件夹内。", "文鲨创作");
                return 1;
            }

            string python = FindPython();
            if (string.IsNullOrWhiteSpace(python))
            {
                MessageBox.Show("找不到 Python 运行环境。当前开发版需要 E:\\python\\pythonw.exe。", "文鲨创作");
                return 1;
            }

            ProcessStartInfo info = new ProcessStartInfo
            {
                FileName = python,
                Arguments = "\"" + runApp + "\"",
                WorkingDirectory = appDir,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            Process.Start(info);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "文鲨创作启动失败");
            return 1;
        }
    }

    private static string FindPython()
    {
        string[] candidates =
        {
            @"E:\python\pythonw.exe",
            @"E:\python\python.exe",
            "pythonw.exe",
            "python.exe"
        };
        foreach (string candidate in candidates)
        {
            if (candidate.Contains(@"\") && File.Exists(candidate))
            {
                return candidate;
            }
            if (!candidate.Contains(@"\"))
            {
                return candidate;
            }
        }
        return "";
    }
}
