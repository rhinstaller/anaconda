#!/usr/bin/perl

print STDERR "Scanning message and help files and surveys which multibyte chars are used...\n";

while (<>) {
    &entry_kanji($_);
}
    
print STDERR "\n$count unique chars\n";

$fillzero = 0;
$charset = 0;
$jismode = $bigfivemode = 0;

print STDERR "Spit out the list of characters being used in the input.\n";

foreach $i (sort(keys(%usedkanji)))
{
   print chr($i / 256) . chr($i % 256) . "\n";
}


sub entry_kanji
{
    local($line) = @_;
    local($i, $len, $c, $kchar);

    $len = length($line);

    for ($i = 0; $i < $len; $i++) {
	$line =~ s/^(.)//;
	$c = ord($1);
	if ($c >= 0xa0 && $c <= 0xff) {
	    $line =~ s/^(.)//;
	    $kchar = $c * 256 + ord($1);
	    $i++;
	    if (!$usedkanji{$kchar}) {
		$usedkanji{$kchar} = 1;
		printf(STDERR "%04x ", $kchar);
		$count++;
	    }
	}
    }
}
