# kachina-tools
Tools for operating a Kachina 505DSP HF Transceiver

I have owned a Kachina 505DSP almost since they were first released. It went on the shelf for a few years but a couple years ago again became my main day to day radio. But the company is gone and the original tools are more or less obsolete (only run on old windows platforms). 

For daily use I use a program called kcat from Dave Freese W1HKJ (https://www.w1hkj.org/). It's quite good and allows control over essentially all the capabilities of the radio. I've contributed a couple small fixes to the code, which Dave incorporated into the current release. But it's 99.99% Dave's work. 

kcat2n3fjp

I wanted a way to sync kcat current band/freq/mode (BFM) with my log program of choice, N3FJP ACLog. I could not find any turn-key solution; N3FJP doesn't know Kachina hardware, and even if it did, there would be a com port sharing issue to deal with, since the 505DSP has literally no front panel - the kcat (or whatever) gui is the only way to operate the radio. But kcat does include code to interact with fldigi, meaning kcat opens a xmlrpc client connection to fldigi to keep fldigi updated with the current state of the rig. I used that, faking out an fldigi xmlrpc server, to catch updates of the radio's BFM and send them to the log. This is a quick and simple solution. At the moment it cannot be used simultaneously with fldigi (since it pretends to be fldigi). But that's not too important, since when using fldigi there IS a path to N3FJP logs to keep them updated. 

So kcat2n3fjp is for the moment the only tool I'm offering, and it's without any warranty or etc. It's written in python and has been tested only in a Linux Mint 22 environment. 

Maybe more tools coming. Though I don't thing there are many Kachina users out there. Please let me know if you stumble across this and are still using your Kachina, whether you want this tool or not. I'd be happy to know there are still some happy owners. 

Bill Bennett N7DZ Tucson AZ
