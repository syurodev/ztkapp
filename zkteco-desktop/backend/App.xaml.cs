using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows;

namespace BlueAngelCare
{
    /// <summary>
    /// Interaction logic for App.xaml
    /// </summary>
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            var filePath = @"D:\file\user.dat";
            var outPath = @"D:\file\users.json";


            //using (var fs = new FileStream(filePath, FileMode.Open))
            //using (var reader = new BinaryReader(fs))
            //{
            //    byte[] bytes = reader.ReadBytes((int)fs.Length);
            //    string text = System.Text.Encoding.ASCII.GetString(bytes);
            //    Utils.WriteLogtxt(text);
            //}


            byte[] bytes = File.ReadAllBytes(filePath);
            string rawText = Encoding.ASCII.GetString(bytes);

            // Loại bỏ ký tự control (dạng không in được)
            string cleaned = Regex.Replace(rawText, @"[^\x20-\x7E\s]", " ");

            // Regex: tách các cặp "Tên nhân viên" và "Mã nhân viên"
            var pattern = @"([A-Z\s]+)\s+(\d{4,})";
            var matches = Regex.Matches(cleaned, pattern);

            var userList = new List<object>();

            foreach (Match match in matches)
            {
                string name = match.Groups[1].Value.Trim();
                string code = match.Groups[2].Value.Trim();

                // Bỏ qua admin hoặc rỗng
                if (!string.IsNullOrEmpty(name) && !name.Equals("ADMIN", StringComparison.OrdinalIgnoreCase))
                {
                    userList.Add(new
                    {
                        EmployeeName = name,
                        EmployeeCode = code
                    });
                }
            }

            // Xuất JSON ra file
            string jsonOutput = JsonSerializer.Serialize(userList, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(outPath, jsonOutput);
        }
    }

    [Serializable]
    public class MyData
    {
        public int Id { get; set; }
        public string Name { get; set; }
    }

}