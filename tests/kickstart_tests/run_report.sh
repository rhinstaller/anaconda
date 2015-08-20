#!/bin/gawk -f

BEGIN {
    printf("\n\n\n%-30s | %-10s | %s\n", "TEST", "RESULT", "EXPLANATION");
    printf("-------------------------------+------------+--------------------------------------------------------\n");
    FS=":"
}
/^RESULT:/ { if ($4 == "Test timed out.") {
                 result = "TIMED OUT";
                 explanation = "";
             } else if (match($0, "Traceback")) {
                 result = "FAILED";
                 explanation = "Traceback";
             } else if (match($0, "SUCCESS")) {
                 result = $3;
                 explanation = "";
             } else {
                 result = $3;
                 explanation = substr($0, index($0, $4), 55);
             }

             printf("%-30s | %-10s | %s\n", $2, result, explanation);
           }
END {
    printf("\n\n");
}
