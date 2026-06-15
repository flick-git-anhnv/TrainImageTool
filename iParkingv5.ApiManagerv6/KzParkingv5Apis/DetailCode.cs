using System;
using System.Collections.Generic;
using System.Text;

namespace iParkingv5.ApiManager.KzParkingv5Apis
{
    public class DetailCode
    {
        public const string ERROR_VALIDATION = "ERROR.VALIDATION.FAILED";

        public const string ERROR_VALIDATION_REQUIRED = "ERROR.ENTITY.VALIDATION.FIELD_REQUIRED";

        public const string ERROR_VALIDATION_SOME_ITEMS_DELETED = "ERROR.ENTITY.VALIDATION.SOME_ITEMS_DELETED";

        public const string ERROR_VALIDATION_DUPLICATED = "ERROR.ENTITY.VALIDATION.FIELD_DUPLICATED";

        public const string ERROR_VALIDATION_NOT_FOUND = "ERROR.ENTITY.VALIDATION.FIELD_NOT_FOUND";

        public const string ERROR_ENTITY_NOT_FOUND_SOME_ITEMS_DELETED = "ERROR.ENTITY.NOT_FOUND.SOME_ITEMS_DELETED";

        public const string ERROR_VALIDATION_NOT_ACTIVE = "ERROR.ENTITY.VALIDATION.FIELD_NOT_ACTIVE";

        public const string ERROR_VALIDATION_INVALID = "ERROR.ENTITY.VALIDATION.FIELD_INVALID";

        public static string ToString(string objectType, string errorMessage)
        {
            switch (errorMessage)
            {
                default:
                    break;
            }
            return "";
        }
    }
}
