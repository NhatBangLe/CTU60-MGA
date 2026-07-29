import TypographyH1 from "@/components/ui/typography.h1";
import TypographyLead from "@/components/ui/typography.lead";
import { useTranslations } from "next-intl";
import { Streamdown } from "streamdown";

const About = () => {
  const aboutTrans = useTranslations("About");

  return (
    <div className="pt-20 pb-4 px-10">
      <TypographyH1 className="uppercase">
        {aboutTrans("aboutProject")}
      </TypographyH1>
      <Streamdown mode="static">{aboutTrans("content")}</Streamdown>
      <TypographyLead className="text-center text-2xl font-semibold text-accent-foreground">
        {aboutTrans("happyAnniversary")}
      </TypographyLead>
    </div>
  );
};

export default About;
