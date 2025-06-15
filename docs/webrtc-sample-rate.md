WebRTC中的Opus编码揭秘
WebRTC中默认是采用Opus编码，Opus编码是由silk编码和celt编码合并在一起，silk编码是由skype公司开源的一种语音编码，特别适合人声，适合于Voip语音通信。celt和mp3,aac类似，适合于传输音乐。Opus编码具备以下特点：

6 kb /秒到510 kb / s的比特率
采样率从8 kHz（窄带）到48 kHz（全频）
帧大小从2.5毫秒到60毫秒
支持恒定比特率（CBR）和可变比特率（VBR）
从窄带到全频段的音频带宽
支持语音和音乐
支持单声道和立体声
支持多达255个频道（多数据流的帧）
可动态调节比特率，音频带宽和帧大小
良好的鲁棒性丢失率和数据包丢失隐藏（PLC）
浮点和定点实现
WebRTC中要使用Opus编码，首先在SDP中要有以下定义：

1
2
3
a=rtpmap:111 opus/48000/2
a=rtcp-fb:111 transport-cc
a=fmtp:111 minptime=10;useinbandfec=1
以上的WebRTC产生的默认配置，这种配置下，音频采样率是48000，音频打包时间是10ms,单声道，编码采用的是Opus里面的silk编码，适合传人声，不适合传音乐。下面我们分别就如何修改采样率，如何修改声道数，如何修改码流做详细介绍。

修改采样率
Opus支持8000，12000,16000，24000，48000 这几种采样率，比如我们现在如果要设置音频采样率为8000，我们应该如何做呢？把SDP修改成如下格式就可以支持8000采样率：

1
2
3
a=rtpmap:111 opus/48000/2
a=rtcp-fb:111 transport-cc 前面两行基本上不会动
a=fmtp:111 minptime=10;useinbandfec=1;maxplaybackrate=8000;
　　不管我们现在采样率要设置为多少，sdp中的前面两行基本上是不会动的。根据抓包分析发现，即使我们现在把采样率修改为8000，音频Rtp中的时间戳还是以960递增。960是在48000采样率情况下20ms声音的信号数。

WebRTC中还支持通信双方以非对称采样率工作。比如A和B通话，A的采样率为48000，B的采样率为8000。当双方采样率不一样时，WebRTC应该如何处理呢？举个例子：

A-----------------> B OfferSDP

1
2
3
a=rtpmap:111 opus/48000/2
a=rtcp-fb:111 transport-cc
a=fmtp:111 minptime=10;useinbandfec=1;maxplaybackrate=16000
B------------------->A AnswerSDP

1
2
3
a=rtpmap:111 opus/48000/2
a=rtcp-fb:111 transport-cc
a=fmtp:111 minptime=10;useinbandfec=1;maxplaybackrate=48000
A用户的采样率为B用户返回的AnswerSDP中的maxplaybackrate，这里是48000，所以A用户音频采样为48000,

同理B用户的采样率为16000

声道数

在a=ftmp这一行中加入stereo=1代表双声道，stereo=0代表单声道，双声道一般用来传音乐,从WebRTC代码中可以发现，当我们设置声道数为2时，opus编码内部将使用celt,代码如下:

config.application = config.num_channels == 1 ? AudioEncoderOpus::kVoip : AudioEncoderOpus::kAudio;

kVoip适合于语音通话，kAudio适合于传输音乐。

码流
在a=ftmp这一行中加入maxaveragebitrate代表接收方能接受的最大码流，单位为bit。比如maxaveragebitrate=64000代表码流为64kbps

开启DTX
DTX 是 Discontinuous Transmission的简称，这个特性是在用户不说话时不传输语音，这样可以节省点带宽。默认WebRTC是不开启这个特性的，要开启DTX，只需要在a=ftmp这一行中加入usedtx=1就行