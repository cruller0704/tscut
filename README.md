# tscut
Python MPEG-TS editing tool.
## Supported formats
- .ts (188-byte packet)
- .m2ts (192-byte packet)

## Usage
```
./tscut.py [-h] [command] ...
```
### Show packet PIDs w/ byte offsets
```
% ./tscut.py pkt -t 188 input.ts
000000000000 [0x0100]
000000000188 [0x0100]
000000000376 [0x0100]
000000000564 [0x0171]
000000000752 [0x0100]
000000000940 [0x0901]
000000001128 [0x0100]
000000001316 [0x0100]
...
```

### Show all PID counts
```
% ./tscut.py pid -t 188 input.ts
[0x0000]         3607
[0x0010]          361
[0x0011]          180
[0x0012]        11698
[0x0014]           72
[0x0023]          488
[0x0024]          361
[0x0027]         1381
...
```

### Show program tree
```
% ./tscut.py prg -t 188 input.ts
Program 31744[0x01F0]
  Stream [0x0100]: type [0x0002]
  Stream [0x0110]: type [0x000F]
  Stream [0x0140]: type [0x000D]
  Stream [0x0160]: type [0x000D]
  Stream [0x0161]: type [0x000D]
  Stream [0x0162]: type [0x000D]
  Stream [0x0170]: type [0x000D]
  Stream [0x0171]: type [0x000D]
...
Program 31745[0x03F0]
  Stream [0x0100]: type [0x0002]
  Stream [0x0110]: type [0x000F]
  Stream [0x0140]: type [0x000D]
  Stream [0x0160]: type [0x000D]
  Stream [0x0161]: type [0x000D]
  Stream [0x0162]: type [0x000D]
  Stream [0x0170]: type [0x000D]
  Stream [0x0171]: type [0x000D]
...
...
```

### Show video pts w/ picture types
```
% ./tscut.py frm -t 188 input.ts
1993.208878,B
1993.242244,B
1993.375711,P
1993.308978,B
1993.342344,B
1993.475811,P
1993.409078,B
1993.442444,B
1993.575911,P
1993.509178,B
1993.542544,B
1993.676011,P
1993.609278,B
1993.642644,B
1993.776111,I
1993.709378,B
...
```

### Trim a TS file
```
./tscut.py cut -t 188 --start 2000.115 --end 2100.015 input.ts output.ts
```

### Concatenate two ts files
```
./tscut.py concat -t 188 input1.ts input2.ts output.ts
```

If two files overlap and the overlap is less than 2 sec, they are concatenated seamlessly (works with BD recorder files).

## Trimming tutorial
1. `ffplay -v quiet -vf "drawtext=fontsize=32:text='\''%{pts} %{pict_type}'\''" input.ts`
2. `./tscut.py cut -t 188 --start A --end B input.ts output.ts` where [A, B)

tscut.py trims ts files, ensuring the output includes [A, B) and both ends are terminated with I-frames.

You can use the ```-r, --relative-time``` option to use any player since pts checking is not required.
