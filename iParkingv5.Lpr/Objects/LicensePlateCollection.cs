using System.Collections;

namespace iParkingv5.Lpr.Objects
{
    public class LicensePlateCollection : CollectionBase
    {
        private int queryTimes = 0;
        private int maxcalls = 0;

        public int QueryTimes { get => queryTimes; set => queryTimes = value; }
        public int CallsLeft { get => maxcalls - queryTimes; }
        public bool IsReachedQuota { get => CallsLeft <= 0; }
        public int Maxcalls { get => maxcalls; set => maxcalls = value; }

        // Constructor
        public LicensePlateCollection()
        {

        }

        public LicensePlate this[int index]
        {
            get { return (LicensePlate)InnerList[index]; }
        }

        // Add
        public void Add(LicensePlate plate)
        {
            InnerList.Add(plate);
        }

        // Remove
        public void Remove(LicensePlate plate)
        {
            InnerList.Remove(plate);
        }
    }

}
