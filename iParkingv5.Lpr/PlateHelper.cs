using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace iParkingv5.Lpr
{
    public static class PlateHelper
    {
        public static string StandardPlate(string plate, bool isRemoveSpecialKey)
        {
            if (string.IsNullOrEmpty(plate))
            {
                return string.Empty;
            }
            //var original = plate;

            //if (plate.Length > 3 && plate[2].ToString() == "-")
            //{
            //    plate = plate.Remove(2, 1);
            //}
            //if (plate.Length > 2)
            //{
            //    if (plate.Substring(0, 2) == "BB")
            //    {
            //        plate = "88" + plate.Substring(2);
            //    }
            //    else if (plate[1] == 'B')
            //    {
            //        plate = plate[0] + "8" + plate.Substring(2);
            //    }
            //    else if (plate[1] == 'D')
            //    {
            //        plate = plate[0] + "0" + plate.Substring(2);
            //    }
            //}
            //plate = plate.Replace('Q', '0');
            //plate = plate.Replace('O', '0');
            //plate = plate.Replace('Z', '2');
            //if (plate.Length > 3)
            //{
            //    if (plate[2] == '8')
            //    {
            //        plate = plate.Substring(0, 2) + "B" + plate.Substring(3);
            //    }
            //    for (int i = 3; i < plate.Length - 1; i++)
            //    {
            //        if (plate[i] == 'D' && i > 3)
            //        {
            //            plate = plate.Substring(0, i) + "0" + plate.Substring(i + 1);
            //        }
            //        else 
            //        if (plate[i] == 'B')
            //        {
            //            plate = plate.Substring(0, i) + "8" + plate.Substring(i + 1);
            //        }
            //    }
            //}
            string output = string.Empty;
            Regex regex = isRemoveSpecialKey ? new Regex("[a-zA-Z0-9;]") : new Regex("[a-zA-Z0-9.-]");
            for (int i = 0; i < plate.Length; i++)
            {
                string plateNumberItem = plate[i].ToString();
                if (regex.IsMatch(plateNumberItem))
                {
                    output += plateNumberItem;
                }
            }
            //if (output.Length > 1)
            //{
            //    if (output.Substring(0, 1) == "B" ||
            //        output.Substring(0, 1) == "C" ||
            //        output.Substring(0, 1) == "G"
            //        )
            //    {
            //        output = "6" + output.Substring(1);
            //    }
            //}
            return output;
        }
        public static string StandardlizePlateNumber(string plate, bool isRemoveSpecialKey)
        {
            if (string.IsNullOrEmpty(plate))
            {
                return string.Empty;
            }
            //if (plate.Length > 3 && plate[2].ToString() == "-")
            //{
            //    plate = plate.Remove(2, 1);
            //}
            //if (plate.Length > 2)
            //{
            //    if (plate.Substring(0, 2) == "BB")
            //    {
            //        plate = "88" + plate.Substring(2);
            //    }
            //    else if (plate[1] == 'B')
            //    {
            //        plate = plate[0] + "8" + plate.Substring(2);
            //    }
            //    else if (plate[1] == 'D')
            //    {
            //        plate = plate[0] + "0" + plate.Substring(2);
            //    }
            //}
            //plate = plate.Replace('Q', '0');
            //plate = plate.Replace('O', '0');
            //plate = plate.Replace('Z', '2');
            //if (plate.Length > 3)
            //{
            //    if (plate[2] == '8')
            //    {
            //        plate = plate.Substring(0, 2) + "B" + plate.Substring(3);
            //    }
            //    for (int i = 3; i < plate.Length - 1; i++)
            //    {
            //        if (plate[i] == 'D' && i > 3)
            //        {
            //            plate = plate.Substring(0, i) + "0" + plate.Substring(i + 1);
            //        }
            //        else if (plate[i] == 'B')
            //        {
            //            plate = plate.Substring(0, i) + "8" + plate.Substring(i + 1);
            //        }
            //    }
            //}
            string output = string.Empty;
            Regex regex = isRemoveSpecialKey ? new Regex("[a-zA-Z0-9;]") : new Regex("[a-zA-Z0-9.-]");
            for (int i = 0; i < plate.Length; i++)
            {
                string plateNumberItem = plate[i].ToString();
                if (regex.IsMatch(plateNumberItem))
                {
                    output += plateNumberItem;
                }
            }

            //if (output.Length > 1)
            //{
            //    if (output.Substring(0, 1) == "B" ||
            //        output.Substring(0, 1) == "C" ||
            //        output.Substring(0, 1) == "G"
            //        )
            //    {
            //        output = "6" + output.Substring(1);
            //    }
            //}
            return output;
        }
    }
}
