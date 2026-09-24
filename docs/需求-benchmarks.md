## Styles数据提取与使用

1、帮我提取/抓取
openrouter网站里，
benchmarks -〉media -〉images -〉Styles 下的数据。


帮我设计一个json schema
分别要存储的数据有：
例如这个页：
https://openrouter.ai/benchmarks/media/images/portraits
Photoreal
Portraits
Why we chose this prompt: Skin and lens realism, natural light and motion, hands and eyes.
Scene
Studio headshot
Studio headshot of a woman in a charcoal blazer against a mid-grey seamless backdrop, lit by a large softbox slightly above and to the left with a soft fill from the right, catchlights in both eyes. An 85mm look with shallow depth of field, skin texture and flyaway hairs kept rather than smoothed.

注意还有这个变体
https://openrouter.ai/benchmarks/media/images/portraits?variant=candid-outdoors

例如：
https://openrouter.ai/benchmarks/media/images/anime-manga
Illustration
Anime and manga
Why we chose this prompt: Line quality, painted backgrounds, dynamic pose.
Subject
Character portrait
Anime illustration, clean cel shading and crisp linework. A pilot pulling her helmet off after a hard landing, hair in disarray with one strand fallen across the eye, a hard-edged cel shadow under the jaw and along the neck. Flight suit collar open, hangar lighting from above, expression tired rather than triumphant.

你先帮我看一下如何设计json schema，定了之后你再开始提取。
注意，出了刚才提取的数据，还需要设计字段：
1、页面的URL
2、aspect_ratio，比例，'2:3'、'1:1'等，这个不是从页面抓取的，后边我们做一个流程来用llm来推测出这个数据
3、创意文案，就是以此为案例，让llm帮忙生成其他prompt的一个用户创意文档说明，类似这种下的value：
```
  {
    label: '头像',
    value: '生成一张以所选主体为唯一焦点的头像肖像。采用肩部以上的近景特写或标准胸像构图，人物面部占据画面主要区域，头顶、发型、双耳和肩部边缘完整可见，不裁切额头、下巴或关键发饰。人物正视镜头或轻微三分之二侧脸，清晰突出五官、发型、肤质与自然神态。保持主体身份和关键外貌特征一致，使用简洁柔和、不过度抢眼的背景，不出现文字、Logo、水印、边框或乱码。'
  },
  {
    label: '证件照',
    value: '生成一张正式、自然、清晰的证件照风格肖像。采用肩部以上至胸部的标准正面构图，人物居中，头顶至上胸区域完整可见，面部正对镜头或仅允许极轻微侧转，双眼清晰、五官完整无遮挡。表情自然端正，服装整洁得体，使用均匀纯色或简洁浅色背景，光线平整柔和、阴影不过重。严格保持主体身份与五官特征一致，不添加文字、Logo、水印、边框或装饰元素。'
  },
  {
    label: '角色设计',
    value: '生成一张完整的单角色设定图。采用全身构图，人物从头顶到脚底完整清晰可见，双脚不得被画面边缘裁切；以自然站姿、轻微动态站姿或符合角色身份的展示姿势呈现。重点清楚展示角色的体型比例、服装层次、鞋履、发型、配饰、道具与关键识别特征。保持人物身份一致，背景采用简洁中性或轻量环境背景并服务于角色展示，不出现文字、标注、Logo、水印或乱码。'
  },
```
抓取完了之后，存储到项目文件夹下，文件名 styles.json

使用 python 实现。
主要流程设计：
1、抓取数据，这个不是一次性的，网站可能会更新，我们跑一次更新一次本地数据即可，存styles.json即可，或者你帮我设计db，先存sqlite，再同步一份到本地json文件，方便查看
2、一个流程，调用llm，方便推测数据，例如 aspect_ratio 、创意文案等，然后生成一个创意模版数据
3、提炼出文档`通用自然语言提示词规范`，这个我们需要讨论一下如何做

抓取出这个数据的作用
1、制作通用自然语言提示词规范
2、做成创意模版数据，方便用户选择



测试 api key，这个你先用着换个key开发测试
sk-****（真实 key 已移除，配置请放 .env 或本地设置）
model
deepseek/deepseek-v4.1-flash



说实话，当前流程已经非常好了，但是我在使用过程中，发现我需要一个主体管理。
帮我做一下数据db设计等，可以添加主体，且在`Prompt 生成器`里可以选择主体，当然选择器里内置一个`自定义`，选了自定义是空的。
主体表设计，可以简单一下，例如
主体类型：人物 / 产品 / 景物 / 品牌
主体名称
主体描述

另外，加了这个数据结构之后，注意页面的内容展示优化修改，例如生成历史中的展示


### 环境变量+设置优化
第一，先帮我加一个变量`LLM_BASE_URL`，扩展一下，用来支持多个PROVIDER，我们这个仅先做openai规范的chat这种的api即可，其他类似responses这种，以及claude的以后再说。
第二，在帮我把当前 OPENROUTER_API_KEY 改成 LLM_API_KEY
第三，在帮我把当前 OPENROUTER_MODEL 改成 LLM_MODEL
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-********
LLM_MODEL=deepseek/deepseek-v4.1-flash

前端，Prompt 生成器 里的模型那个input帮我去掉

前端，帮我做一个设置，你看看是设计在页面左上角还是哪儿，这里可以设置这环境变量里的三个，这个帮我做一个db存储，设计一下数据结构。这里说明一下，支持设置多个，且能设置用那个llm设置，这种都是大家默认的一些设计，你看看db如何设计表结构，当然，这个db，我希望你帮我重新做一个db，例如脚setting.db或者secret.db或者personal.db，原因是这样的，我会把项目上传github，公开项目，我希望其他人开箱即用，能用到我们的一些内置style，场景库、主体库等。另外，再帮我把`生成历史`这个数据转到我们这个新增的库里，这个不能共享，后续也需要把这个db再.gitignore里写一下。