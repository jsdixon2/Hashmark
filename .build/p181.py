# p181 (owner: War Room big board arrows did nothing): prospect ids look like "c:5189530", and the ▲▼ handler split
# "c:5189530:-1" on every colon (id "c", step 5189530), so it never found the player. Split on the last colon only.
p = "index.html"; s = open(p).read()
a = '''const [id,d]=b.dataset.wmv.split(":");const B=cur()'''
b = '''const wv=b.dataset.wmv,k=wv.lastIndexOf(":"),id=wv.slice(0,k),d=wv.slice(k+1);const B=cur()'''
assert s.count(a) == 1; s = s.replace(a, b)
open(p, "w").write(s); print("p181 ok")
