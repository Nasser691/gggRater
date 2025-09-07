import discord
from discord.ext import commands
import os
import threading
from flask import Flask
import json

# ====== إعدادات Flask ======
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

# تشغيل Flask في Thread ثاني
threading.Thread(target=run_web).start()

# ====== إعدادات البوت ======
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== ملف تخزين التقييمات ======
DATA_FILE = "ratings.json"

# تحميل البيانات إذا الملف موجود
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        ratings = json.load(f)
else:
    ratings = {}

def save_ratings():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(ratings, f, ensure_ascii=False, indent=4)

STORIES_CHANNEL_ID = 1329119283686670427  # <<<< ID الروم

# ====== تحديد الحلقة الأخيرة عند تشغيل البوت ======
episode_counter = 0
if ratings:
    episodes_numbers = []
    for data in ratings.values():
        title = data["title"]  # مثال: "الموسم الرابع - الحلقة 2"
        if "الحلقة" in title:
            try:
                number = int(title.split("الحلقة")[1].strip())
                episodes_numbers.append(number)
            except:
                pass
    if episodes_numbers:
        episode_counter = max(episodes_numbers)

# ====== الواجهات ======
class RatingView(discord.ui.View):
    def __init__(self, story_id, story_title):
        super().__init__(timeout=None)
        self.story_id = story_id
        self.story_title = story_title
        # أزرار التقييم
        for i in range(1, 11):
            self.add_item(RatingButton(i, story_id, story_title))
        # زر عرض النتائج للحلقة
        self.add_item(ResultsButton(story_id))
        # زر عرض كل الحلقات
        self.add_item(AllResultsButton())

class RatingButton(discord.ui.Button):
    def __init__(self, number, story_id, story_title):
        super().__init__(style=discord.ButtonStyle.primary, label=str(number))
        self.number = number
        self.story_id = story_id
        self.story_title = story_title

    async def callback(self, interaction: discord.Interaction):
        if self.story_id not in ratings:
            ratings[self.story_id] = {"title": self.story_title, "scores": {}}
        ratings[self.story_id]["scores"][str(interaction.user.id)] = self.number
        save_ratings()
        await interaction.response.send_message(
            f"✅ قيّمت **{self.story_title}** بـ {self.number}/10",
            ephemeral=True
        )

class ResultsButton(discord.ui.Button):
    def __init__(self, story_id):
        super().__init__(style=discord.ButtonStyle.success, label="📊 Show Results")
        self.story_id = story_id

    async def callback(self, interaction: discord.Interaction):
        data = ratings.get(self.story_id)
        if not data or not data["scores"]:
            await interaction.response.send_message(
                "⚠️ مافي تقييمات للحلقة هذه للحين.",
                ephemeral=True
            )
            return

        scores = data["scores"]
        avg = sum(scores.values()) / len(scores)
        result_text = "\n".join(
            [f"<@{uid}> ⭐ {score}/10" for uid, score in scores.items()]
        )

        embed = discord.Embed(
            title=f"📊 نتائج {data['title']}",
            description=f"**المتوسط:** {avg:.1f}/10\n\n{result_text}",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

class AllResultsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="📑 All Episodes Results")

    async def callback(self, interaction: discord.Interaction):
        if not ratings:
            await interaction.response.send_message("⚠️ ما في أي تقييمات للحين.", ephemeral=True)
            return

        msg = ""
        for story_id, data in ratings.items():
            scores = data["scores"]
            if scores:
                avg = sum(scores.values()) / len(scores)
                msg += f"- **{data['title']}**: {avg:.1f}/10 ({len(scores)} تقييم)\n"

        if not msg:
            msg = "⚠️ ما في أي تقييمات للحلقات للحين."

        embed = discord.Embed(
            title="📑 نتائج جميع الحلقات",
            description=msg,
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ====== الأحداث ======
@bot.event
async def on_message(message):
    global episode_counter
    if message.author.bot:
        return

    # ✅ فقط للصور والفيديوهات في الروم المحدد
    if message.channel.id == STORIES_CHANNEL_ID and message.attachments:
        episode_counter += 1
        story_id = str(message.id)
        story_title = f"الموسم الرابع - الحلقة {episode_counter}"
        ratings[story_id] = {"title": story_title, "scores": {}}
        save_ratings()
        view = RatingView(story_id, story_title)
        await message.channel.send(
            f"📖 تم نشر: **{story_title}**\n⬇️ اختر تقييمك:",
            view=view
        )

    await bot.process_commands(message)

# ====== أوامر البوت ======
@bot.command()
async def results(ctx, episode: int = None):
    if not ratings:
        await ctx.send("⚠️ مافي أي تقييمات للحين.")
        return

    if episode is None:
        msg = "📊 **نتائج التقييمات:**\n"
        for story_id, data in ratings.items():
            scores = data["scores"]
            if scores:
                avg = sum(scores.values()) / len(scores)
                msg += f"- {data['title']}: {avg:.1f}/10 ({len(scores)} تقييم)\n"
        await ctx.send(msg)
    else:
        for story_id, data in ratings.items():
            if f"الحلقة {episode}" in data["title"]:
                scores = data["scores"]
                if not scores:
                    await ctx.send(f"⚠️ مافي تقييمات للحلقة {episode}.")
                    return
                avg = sum(scores.values()) / len(scores)
                users_list = "\n".join([f"<@{uid}> ⭐ {score}/10" for uid, score in scores.items()])
                embed = discord.Embed(
                    title=f"📊 نتائج {data['title']}",
                    description=f"**المتوسط:** {avg:.1f}/10\n\n{users_list}",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                return
        await ctx.send(f"⚠️ ما لقيت الحلقة {episode}.")

# ====== تشغيل البوت ======
bot.run(os.environ["DISCORD_BOT_TOKEN"])
