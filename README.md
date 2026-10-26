# retrievalscore

**给检索结果排个可解释的序。**

`retrievalscore` —— 按查询词覆盖、来源可信度与新鲜度给检索结果打分，输出每一项的得分构成。

- 零依赖，Python 3.10+ 标准库即可运行
- 单文件，`retrievalscore.py` 拷走就能用
- 不联网、不写文件

<!-- ipos:install -->
## 安装

零依赖，Python 3.10+ 即可：

```bash
pip install mahmadwile-retrievalscore
```

装完直接用命令名调用：

```bash
retrievalscore --help
```

也可以不用安装，直接把 `retrievalscore.py` 拷走用——它只依赖标准库。

## 为什么需要它

现有重排器只给一个分数；retrievalscore 把分数拆成覆盖、可信度、新鲜度三项并列出来，排序结果可以逐项复核。

它遵守下面几条自己定的规矩：

1. **分数必须拆开**。只给一个总分的重排器没法排查问题。
2. **规则写在配置里**。权重、来源可信度、时效衰减都能改，改完立刻生效。
3. **不打分无理由**。查不到就明说查不到，不给一个编出来的分数。

## 用法

```bash
python retrievalscore.py --query "时间戳格式" --candidates results.json
python retrievalscore.py --query "..." --candidates results.json --json
```

加 `--json` 可以拿到机器可读的结果，便于接到流水线里。

## 已知局限

- 可信度表靠人工维护，没有登记的域名一律拿默认值。
- 分词用 2-gram，不带词典，中文分词精度有限。
- 不联网抓取正文，只用你给它的标题、摘要与链接。

## 跑测试

```bash
python test_retrievalscore.py
```

测试用独立的断言与临时数据，不污染工作目录。

## 来源与参考

- Python 标准库文档：<https://docs.python.org/3/>
- GitHub 仓库：<https://github.com/mahmadwile/retrievalscore>

---

## 关于作者

mahmadwile 做检索排序可解释性相关的问题。这个工具先替你回答一个具体问题，再谈别的。

- 个人主页：<https://mahmadwile.github.io>
- 仓库：<https://github.com/mahmadwile/retrievalscore>

## 许可

MIT，见 [LICENSE](LICENSE)。
