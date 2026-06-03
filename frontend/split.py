import os

src_file = r"c:\Users\hp\Desktop\AI STEM Lab Assistant\frontend\src\pages\Dashboard.tsx"
out_dir_dash = r"c:\Users\hp\Desktop\AI STEM Lab Assistant\frontend\src\components\dashboard"
out_dir_physics = r"c:\Users\hp\Desktop\AI STEM Lab Assistant\frontend\src\components\physics"

os.makedirs(out_dir_dash, exist_ok=True)
os.makedirs(out_dir_physics, exist_ok=True)

with open(src_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def write_component(name, start_line, end_line, out_path, extra_imports=""):
    # lines are 0 indexed in python, so start_line - 1
    content = lines[start_line-1:end_line]
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('import React, { useState, useEffect, useRef, Suspense, lazy } from "react";\n')
        f.write('import { motion, AnimatePresence } from "framer-motion";\n')
        f.write('import { Link, useNavigate } from "react-router-dom";\n')
        f.write('import { AreaChart, Area, ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";\n')
        f.write('import { Zap, Award, Trophy, Flame, Camera, Bot, Play, Pause, ArrowRight, Activity, CheckCircle2, Atom, Clock, Lock, Check, BookOpen, FlaskConical, Settings, Target, Brain, Star, Sparkles, RefreshCw, Sliders } from "lucide-react";\n')
        f.write('import { pushNotification } from "../../lib/notificationStore";\n')
        f.write('import { useUserStore } from "../../store/useUserStore";\n')
        f.write('import { usePhysicsStore } from "../../store/usePhysicsStore";\n')
        f.write(extra_imports + '\n')
        f.writelines(content)

# DashboardHome
write_component("DashboardHome", 44, 280, os.path.join(out_dir_dash, "DashboardHome.tsx"))

# AITutorPageWrapper
write_component("AITutorPageWrapper", 282, 370, os.path.join(out_dir_dash, "AITutorPageWrapper.tsx"), 'const AITutorPanel = lazy(() => import("../ai-tutor/AITutorPanel"));\n')

# PhysicsLabPageWrapper
write_component("PhysicsLabPageWrapper", 373, 1468, os.path.join(out_dir_physics, "PhysicsLabPageWrapper.tsx"))

# ChallengesPage
write_component("ChallengesPage", 1471, 1576, os.path.join(out_dir_dash, "ChallengesPage.tsx"))

# AchievementsPage
write_component("AchievementsPage", 1579, 1982, os.path.join(out_dir_dash, "AchievementsPage.tsx"))

# ExperimentsCatalog
write_component("ExperimentsCatalog", 1985, 2221, os.path.join(out_dir_dash, "ExperimentsCatalog.tsx"))

print("Splitting completed successfully.")
